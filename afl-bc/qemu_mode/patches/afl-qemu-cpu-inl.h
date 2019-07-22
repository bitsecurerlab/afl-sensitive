/*
   american fuzzy lop - high-performance binary-only instrumentation
   -----------------------------------------------------------------

   Written by Andrew Griffiths <agriffiths@google.com> and
              Michal Zalewski <lcamtuf@google.com>

   Idea & design very much by Andrew Griffiths.

   Copyright 2015 Google Inc. All rights reserved.

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at:

     http://www.apache.org/licenses/LICENSE-2.0

   This code is a shim patched into the separately-distributed source
   code of QEMU 2.2.0. It leverages the built-in QEMU tracing functionality
   to implement AFL-style instrumentation and to take care of the remaining
   parts of the AFL fork server logic.

   The resulting QEMU binary is essentially a standalone instrumentation
   tool; for an example of how to leverage it for other purposes, you can
   have a look at afl-showmap.c.

 */

#include <sys/shm.h>
#include "../../config.h"

/***************************
 * VARIOUS AUXILIARY STUFF *
 ***************************/

/* A snippet patched into tb_find_slow to inform the parent process that
   we have hit a new block that hasn't been translated yet, and to tell
   it to translate within its own context, too (this avoids translation
   overhead in the next forked-off copy). */

#define AFL_QEMU_CPU_SNIPPET1 do { \
    afl_request_tsl(pc, cs_base, flags); \
  } while (0)

/* This snippet kicks in when the instruction pointer is positioned at
   _start and does the usual forkserver stuff, not very different from
   regular instrumentation injected via afl-as.h. */

#define AFL_QEMU_CPU_SNIPPET2 do { \
    if(tb->pc == afl_entry_point) { \
      afl_setup(); \
      afl_forkserver(env); \
    } \
    afl_maybe_log(tb->pc); \
  } while (0)

/* We use one additional file descriptor to relay "needs translation"
   messages between the child and the fork server. */

#define TSL_FD (FORKSRV_FD - 1)

/* This is equivalent to afl-as.h: */

static unsigned char *afl_area_ptr;

/* Exported variables populated by the code patched into elfload.c: */

abi_ulong afl_entry_point, /* ELF entry point (_start) */
          afl_start_code,  /* .text start pointer      */
          afl_end_code;    /* .text end pointer        */

/* Set on the child in forkserver mode: */

static unsigned char afl_fork_child;


/* the id for multiple CBs*/
static int cb_id = -1;

/*current TSL_FD for the specific CB*/
static int cur_tsl_fd;

/* Instrumentation ratio: */

static unsigned int afl_inst_rms = MAP_SIZE;

/* Function declarations. */

static void afl_setup(void);
static void afl_forkserver(CPUArchState*);
static inline void afl_maybe_log(abi_ulong);

static void afl_wait_tsl(CPUArchState*, int);
static void afl_request_tsl(target_ulong, target_ulong, uint64_t);

static TranslationBlock *tb_find_slow(CPUArchState*, target_ulong,
                                      target_ulong, uint64_t);


/* Data structure passed around by the translate handlers: */

struct afl_tsl {
  target_ulong pc;
  target_ulong cs_base;
  uint64_t flags;
};


/*************************
 * ACTUAL IMPLEMENTATION *
 *************************/


/* Set up SHM region and initialize other stuff. */

static void afl_setup(void) {
  //fprintf(stderr, "[&]afl_setup\n");
  char *id_str = getenv(SHM_ENV_VAR);
  int shm_id = -1;
  if(id_str)
  {
    shm_id = atoi(id_str);
    cb_id = 0;
  }
  else
  {

    if ((read(FORKSRV_FD, &cb_id, 4) != 4) || (read(FORKSRV_FD, &shm_id, 4) != 4))
      return;      
  }
  if(cb_id != -1)
  {
    cur_tsl_fd = TSL_FD - cb_id;
  }else exit(1);

  if(shm_id != -1)
  {
    afl_area_ptr = shmat(shm_id, NULL, 0);

    if (afl_area_ptr == (void*)-1) exit(1);

  }else exit(1);


  char *inst_r = getenv("AFL_INST_RATIO");

  if (inst_r) {

    unsigned int r;

    r = atoi(inst_r);

    if (r > 100) r = 100;
    if (!r) r = 1;

    afl_inst_rms = MAP_SIZE * r / 100;

  }



  if (getenv("AFL_INST_LIBS")) {

    afl_start_code = 0;
    afl_end_code   = (abi_ulong)-1;

  }
  //fprintf(stderr, "[&]afl_start_code: 0x%x | afl_end_code: 0x%x\n", afl_start_code, afl_end_code);
}


/* Fork server logic, invoked once we hit _start. */

static void afl_forkserver(CPUArchState *env) {
  //fprintf(stderr, "[%]afl_forkserver\n");
  static unsigned char tmp[4];

  if (!afl_area_ptr) return;

  /* Tell the parent that we're alive. If the parent doesn't want
     to talk, assume that we're not running in forkserver mode. */

  if (write(FORKSRV_FD + 1, tmp, 4) != 4) return;

  /* All right, let's await orders... */

  //fprintf(stderr, "[%]#0\n");
  while (1) {

    pid_t child_pid;
    int status, t_fd[2];

    /* Whoops, parent dead? */

    if (read(FORKSRV_FD, tmp, 4) != 4) exit(2); //forked exec start to run 

    /* Establish a channel with child to grab translation commands. We'll 
       read from t_fd[0], child will write to TSL_FD. */

    // if (pipe(t_fd) || dup2(t_fd[1], TSL_FD) < 0) exit(3);
    if (pipe(t_fd) || dup2(t_fd[1], cur_tsl_fd) < 0) exit(3);
    close(t_fd[1]);

    child_pid = fork();
    if (child_pid < 0) exit(4);

    if (!child_pid) {

      /* Child process. Close descriptors and run free. */

      afl_fork_child = 1;
      close(FORKSRV_FD);
      close(FORKSRV_FD + 1);
      close(t_fd[0]);
      return;

    }

    /* Parent. */

    // close(TSL_FD);
    close(cur_tsl_fd);

    if (write(FORKSRV_FD + 1, &child_pid, 4) != 4) exit(5);

    /* Collect translation requests until child dies and closes the pipe. */
    //fprintf(stderr, "[%]#1\n");
    afl_wait_tsl(env, t_fd[0]);

    /* Get and relay exit status to parent. */
    //fprintf(stderr, "[%]#1\n");
    if (waitpid(child_pid, &status, WUNTRACED) < 0) exit(6);
    if (write(FORKSRV_FD + 1, &status, 4) != 4) exit(7);

  }

}


/* The equivalent of the tuple logging routine from afl-as.h. */

static inline void afl_maybe_log(abi_ulong cur_loc) {

  static abi_ulong prev_loc;

  /* Optimize for cur_loc > afl_end_code, which is the most likely case on
     Linux systems. */

  if (cur_loc > afl_end_code || cur_loc < afl_start_code || !afl_area_ptr)
    return;

  /* Looks like QEMU always maps to fixed locations, so we can skip this:
     cur_loc -= afl_start_code; */

  /* Instruction addresses may be aligned. Let's mangle the value to get
     something quasi-uniform. */

  cur_loc  = (cur_loc >> 4) ^ (cur_loc << 8);
  cur_loc &= MAP_SIZE - 1;

  /* Implement probabilistic instrumentation by looking at scrambled block
     address. This keeps the instrumented locations stable across runs. */

  if (cur_loc >= afl_inst_rms) return;

  afl_area_ptr[cur_loc ^ prev_loc]++;
  prev_loc = cur_loc >> 1;

}


/* This code is invoked whenever QEMU decides that it doesn't have a
   translation of a particular block and needs to compute it. When this happens,
   we tell the parent to mirror the operation, so that the next fork() has a
   cached copy. */

static void afl_request_tsl(target_ulong pc, target_ulong cb, uint64_t flags) {

  struct afl_tsl t;
  // fprintf(stderr, "[#]afl_request_tsl(pc=0x%x, cb=0x%x, )\n", pc, cb);
  if (!afl_fork_child) return;
  // fprintf(stderr, "[#]fork_child\n");
  t.pc      = pc;
  t.cs_base = cb;
  t.flags   = flags;
  // fprintf(stderr, "[#]->write(cur_tsl_fd=%d,,)\n", cur_tsl_fd);
  // if (write(TSL_FD, &t, sizeof(struct afl_tsl)) != sizeof(struct afl_tsl))
  if (write(cur_tsl_fd, &t, sizeof(struct afl_tsl)) != sizeof(struct afl_tsl))
    return;
  // fprintf(stderr, "[#]end-\n");
}


/* This is the other side of the same channel. Since timeouts are handled by
   afl-fuzz simply killing the child, we can just wait until the pipe breaks. */

static void afl_wait_tsl(CPUArchState *env, int fd) {

  struct afl_tsl t;
  // fprintf(stderr, "[*]afl_wait_tsl()\n");
  while (1) {
    // fprintf(stderr, "[*]while starts\n");
    /* Broken pipe means it's time to return to the fork server routine. */

    if (read(fd, &t, sizeof(struct afl_tsl)) != sizeof(struct afl_tsl))
      break;
    // fprintf(stderr, "[*]t.pc: 0x%x | t.cs_base: 0x%x\n", t.pc, t.cs_base);
    //do not cache for dynamically generated code
    if((t.pc >= afl_start_code) && (t.pc <= afl_end_code))
      tb_find_slow(env, t.pc, t.cs_base, t.flags);
    // else
      // fprintf(stderr, "[*]no cache for JIT code\n");
    // fprintf(stderr, "[*]while ends--\n");
  }

  close(fd);
  // fprintf(stderr, "[*]ret\n");
}

