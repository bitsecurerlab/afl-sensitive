#!/usr/bin/env python
import logging
logging.basicConfig(format='%(levelname)-7s | %(asctime)-23s | %(name)-12s | %(message)s')

l = logging.getLogger("afl.main")

l.setLevel(logging.INFO)

import os
import sys
import subprocess
import time
# import socket

import threading
import argparse
import shutil

from multiprocessing import Process

import raise_stats



root_dir = 'ROOT_DIR'   # to implement

# 
cbs_dir = os.path.join(root_dir, 'cbs') 



logs_dir = None
default_outputs_dir = None
co_outputs_dir = None
shared_outputs_dir = None
local_outputs_dir = None
testcases_dir = None
stats_dir = None
dicts_dir = None



afl_list = ['bc', 'ct', 'ma', 'mw', 'n2', 'n4', 'n8']


def system_clean(arg):
    p = subprocess.Popen(arg, shell=True, close_fds=True)
    p.wait()
    return p.returncode

def is_crash_found(state_fp):
    stats = []
    threshhold = 10

    with open(state_fp, 'r') as f:
        stats = f.readlines()
    for line in stats:
        key, val = line.split(':', 1)
        key = key.strip()
        val = val.strip()
        if key == 'unique_crashes':
            if int(val) >= threshhold:
                return True
            else:
                return False
    return False


def check_afl_on(afl_banner):
    cmd = 'ps -ef|grep afl-fuzz|grep {}'.format(afl_banner)
    out = subprocess.check_output(cmd, shell=True)
    pid = -1
    for line in out.splitlines():
        if 'afl-fuzz' in line:
            pid = int(line.split(None)[1])
            break
    return pid


def ensure_dir(dname):
    if not os.path.isdir(dname):
        try:
            os.mkdir(dname)
        except OSError as e:
            import errno
            if e.errno != errno.EEXIST:
                raise 




class FuzzOne():
    def __init__(self, pro_name, cont_name, afl_version, seq, timeout=1000):

        self.cb_name = pro_name
        self.cont_name = cont_name
        self.cb_dir = os.path.join(cbs_dir, pro_name)
        self.cb_bins_dir = os.path.join(self.cb_dir, 'bins')
        self.cb_bin_paths = []
        
        self.afl_ver = afl_version
        self.seq = seq
        self.__locate_cb_bins__()

        self.timeout = str(timeout)
        self.proc = None

    def setup(self):        
        self.ins_name = 'fuzzer-{}-{}_{}{:0>2}'.format(self.cb_name, self.cont_name, self.afl_ver, self.seq) 

        cb_out_dir = default_outputs_dir  
        self.__setup_cb_output__(cb_out_dir)   
        
        cb_sync_dir = default_outputs_dir
        self.__setup_cb_syncdir__(cb_sync_dir)

        self.__show__()

    def __show__(self):
        i_str =  ['fuzz class: {}'.format(self.__class__.__name__)]
        i_str += ['cb_name: {}'.format(self.cb_name)]
        i_str += ['cb_dir: {}'.format(self.cb_dir)]
        i_str += ['cb_bins_dir: {}'.format(self.cb_bins_dir)]
        i_str += ['cb_bin_paths: {}'.format(self.cb_bin_paths)]
        i_str += ['ins_name: {}'.format(self.ins_name)]
        i_str += ['output_dir: {}'.format(self.output_dir)]
        i_str += ['sync_dir: {}'.format(self.sync_dir)]
        l.debug("%s", i_str)

    def __locate_cb_bins__(self):
        names = []
        for _root, _dirs, files in os.walk(self.cb_bins_dir):
            for name in files:
                if 'patched' not in name and not name.endswith('.zip'):
                    # system_clean('chmod +x ' + os.path.join(self.cb_bins_dir, name))
                    names.append(name)
        sorted_names = sorted(names)
        for name in sorted_names:
            bin_path = os.path.join(self.cb_bins_dir, name)
            self.cb_bin_paths.append(bin_path)

        # if 'tcpdump' in self.cb_name:
            # pass



    def __setup_cb_output__(self, cb_out_dir):        
        if not os.path.exists(cb_out_dir):
            os.mkdir(cb_out_dir)
        self.output_dir = cb_out_dir 

    def __setup_cb_syncdir__(self, cb_sync_dir):
        if not os.path.exists(cb_sync_dir):
            os.mkdir(cb_sync_dir)
        self.sync_dir = cb_sync_dir



    def check_crash(self):

        its_stats_dir = os.path.join(self.output_dir, self.ins_name)
        l.info('checking crashes for {}'.format(its_stats_dir))

        state_filepath = os.path.join(its_stats_dir, 'fuzzer_stats')
        if os.path.isfile(state_filepath):
            if is_crash_found(state_filepath):
                return True
        else:
            l.error('no fuzzer_stats file found in {}'.format(its_stats_dir))
        return False

    @staticmethod
    def add_paras(csid):
        if 'readelf' in csid:
            return ['-a', '@@']
        elif 'tcpdump' in csid:
            return ['-r', '@@']
        elif 'strings' in csid:
            return ['-a', '@@']
        elif 'file' in csid:
            return ['@@']
        elif 'objdump' in csid:
            return ['-D', '@@']
        elif 'gzip' in csid:
            return ['-c', '-d', '@@']
        elif 'info2cap' in csid: #infotocap
            return ['-C', '@@']
        elif 'nm' in csid:
            return ['-C', '@@']
        else:
            return ['@@']


    def start_fuzzing(self):
        cur_dir = os.getcwd()
        afl_dir = os.path.join(cur_dir, 'afl-{}'.format(self.afl_ver))
        os.chdir(afl_dir)
        seq = self.seq
        fd_stderr = open(os.path.join(logs_dir, 'afl_stderr_{}{:0>2}'.format(self.afl_ver, seq)), 'w')
        fd_stdout = open(os.path.join(logs_dir, 'afl_stdout_{}{:0>2}'.format(self.afl_ver, seq)), 'w')

        # my_env = os.environ
        # if 'tcpdump' in self.cb_name:
        #     my_env['AFL_NO_FORKSRV'] = '1'
        #     self.timeout = '1000'

        args = ['./afl-fuzz',  '-Q']
        args += ['-m', 'none']
        args += ['-t', self.timeout]
        args += ['-i', testcases_dir]
        args += ['-o', self.output_dir]
        args += ['-s', self.sync_dir]
        args += ['-l', local_outputs_dir]

        if self.afl_ver == 'filter':
           args += ['-r']

        if seq == 0:
            args += ['-M', self.ins_name]
        else:
            args += ['-S', self.ins_name]


        args += [' '.join(self.cb_bin_paths)]

        args += self.add_paras(self.cb_name)

        

        l.info("%s", args)

        self.proc = subprocess.Popen(args, stdout=fd_stdout, stderr=fd_stderr, env=my_env, close_fds=True)

        os.chdir(cur_dir)

    def stop(self):
        l.warning('-> {} on {} terminates'.format(self.ins_name, self.cb_name))
        self.proc.terminate()



class FuzzFilter(FuzzOne):

    def __init__(self, pro_name, cont_name):
        FuzzOne.__init__(self, pro_name, cont_name, 'filter', 0, 2000)

    def setup(self):
        self.ins_name = 'fuzzer-{}-{}_filter'.format(self.cb_name, self.cont_name)

        cb_out_dir = co_outputs_dir
        self.__setup_cb_output__(cb_out_dir)   

        # its_outputs_dir = os.path.join(cb_out_dir, self.ins_name)
        # setup_tmpfs(its_outputs_dir, '1500M')

        cb_sync_dir = default_outputs_dir
        self.__setup_cb_syncdir__(cb_sync_dir)

        self.__show__()



def setup_dirs(round_id, mode, csid):
    global default_outputs_dir
    global co_outputs_dir
    global shared_outputs_dir
    global local_outputs_dir
    global logs_dir
    global testcases_dir
    global stats_dir
    global dicts_dir

    round_dir = os.path.join(root_dir, 'exps', 'round_{}'.format(round_id))
    ensure_dir(round_dir)

    mode_dir = os.path.join(round_dir, 'mode_{}'.format(mode))
    ensure_dir(mode_dir)

    cb_dir = os.path.join(mode_dir, csid)
    ensure_dir(cb_dir)

    default_outputs_dir = os.path.join(cb_dir, 'outputs')
    ensure_dir(default_outputs_dir)

    co_outputs_dir = os.path.join(cb_dir, 'co_outputs')
    ensure_dir(co_outputs_dir)

    logs_dir = os.path.join(cb_dir, 'logs')
    ensure_dir(logs_dir)

    stats_dir = os.path.join(cb_dir, 'stats')
    ensure_dir(stats_dir)

    tmp = os.path.join('/tmp', 'fuzz')
    ensure_dir(tmp)
    tmp = os.path.join(tmp, '{}_{}_{}'.format(round_id, mode, csid))
    ensure_dir(tmp)
    tmp = os.path.join(tmp, 'local_outputs')
    shutil.rmtree(tmp, ignore_errors=True)
    ensure_dir(tmp)
    local_outputs_dir = tmp


    testcases_dir = os.path.join(cbs_dir, csid, 'seeds')
    dicts_dir = os.path.join(cbs_dir, csid, 'dicts')

    shared_outputs_dir = default_outputs_dir
    




def start_driller(target_fuzzer):

    binary_path = target_fuzzer.cb_bin_paths[0]
    fuzzer_id = target_fuzzer.ins_name
    in_dir = target_fuzzer.output_dir
    out_dir = target_fuzzer.sync_dir

    args = ['/bin/bash', '-c', 'source /usr/local/bin/virtualenvwrapper.sh && workon angr && ./start_driller.py --b {} --f {} --i {} --o {}'.format(binary_path, fuzzer_id, in_dir, out_dir)]
    p = subprocess.Popen(args)  

    time.sleep(1)
    cmd = 'ps -ef|grep python '
    out = subprocess.check_output(cmd, shell=True)

    pid = -1
    for line in out.splitlines():
        if 'start_driller' in line:
            pid = int(line.split(None)[1])
            break
    l.info("%s in %d", args, pid)
    return pid


def stop_driller(d_pid):
    cmd = 'kill {}'.format(d_pid)
    system_clean(cmd)
    l.warning('-> driller terminates')


def main():
    

    parser = argparse.ArgumentParser(description='start afl and driller (maybe)')
    
    parser.add_argument('--csid', metavar='CSID', required=True, type=str,
        help='csid')

    parser.add_argument('--mode', metavar='MODE', required=False, type=str,
        default='2:0:0:0:0:0:0', help='str(num_bc:num_ct:num_ma:num_mw:num_n2:num_n4:num_n8)')

    parser.add_argument('--round', metavar='ROUND', required=False, type=int,
        default=0, help='round of the exp')

    feature_parser = parser.add_mutually_exclusive_group(required=False)
    feature_parser.add_argument('--angr', dest='angr_on', action='store_true')
    feature_parser.add_argument('--no-angr', dest='angr_on', action='store_false')
    parser.set_defaults(angr_on=False)

    args = parser.parse_args()

    round_id = '{:0>2}'.format(args.round)
    csid = args.csid

    setup_dirs(round_id, args.mode.replace(':', ''), csid)

    angr_on = args.angr_on

    if angr_on:
        l.error("sorry, currently angr not supported")

    mode = args.mode.strip().split(':')
    group_vols = [int(n) for n in mode]

    afl_total_num = sum(group_vols)
    

    group_cnt = len(afl_list)    

    group_dict = dict([])

    # cname = socket.gethostname()
    # cname = os.getenv('HOSTNAME') 
    cname = 'hpcc' 

    fuzz_proc_list = []
    
    raise_stats.g_task_name = '{}-{}'.format(csid, cname)
    raise_stats.g_shared_outputs = shared_outputs_dir
    raise_stats.g_stats_dir = stats_dir
    raise_stats.g_co_outputs = co_outputs_dir

    for i, ver in enumerate(afl_list):
        vol = group_vols[i]
        fuzz_list = range(vol)
        for seq in range(vol):
            fuzz_list[seq] = FuzzOne(csid, cname, ver, seq)
            fuzz_list[seq].setup()
            fuzz_list[seq].start_fuzzing()
        group_dict[ver] = fuzz_list

    fuzz_filter = FuzzFilter(csid, cname)
    fuzz_filter.setup()
    fuzz_filter.start_fuzzing()

    group_dict['filter'] = [fuzz_filter]


    t_stop = threading.Event()
    t_stats = threading.Thread(target=raise_stats.do_loop_thread, args=(t_stop,))
    t_stats.start()
    
    driller_pid = None
    if angr_on:
        driller_pid = start_driller(fuzz_filter)

    # keep running for 168 hours until finding no less than 10 unique crashes
    for i in range(168 * 6):
        try:
            time.sleep(10 * 60)
            l.info('**fuzzing...')
            if fuzz_filter.check_crash():
                l.info('**enough crashes found')
                break
        except KeyboardInterrupt:
            break
    l.warning('**terminating...')

    for fl in group_dict.values():
        for f in fl:
            f.stop()

    t_stop.set()
    t_stats.join()   

    if angr_on and driller_pid != -1:
        stop_driller(driller_pid)

    l.warning('**exit...')

if __name__ == '__main__':
    main()
    