import logging
l = logging.getLogger("afl.stats")
l.setLevel(logging.INFO)

import os
import sys
import time
import json

import subprocess
from sets import Set

g_stats_raise_sec = 60 * 5



g_shared_outputs = 'Unknown'
g_stats_dir = 'Unknown'
g_co_outputs = 'Unknown'
g_task_name = 'Unknown'


g_code_block = None


def ensure_dir(dname):
    if not os.path.isdir(dname):
        os.makedirs(dname)

def atomic_write(fp, text):
    tmp_file = '{}_tmp'.format(fp)
    f = open(tmp_file, 'w+')
    f.write(text)
    f.flush()
    os.fsync(f.fileno())
    f.close()
    os.rename(tmp_file, fp)


def parse_stats(stats_fp):
    l.info('parsing stats for {}...'.format(stats_fp))
    stats = dict()
    lines = []
    with open(stats_fp, 'r') as f:
        lines = f.readlines()
    for line in lines:
        key, val = line.split(':', 1)
        key = key.strip()
        val = val.strip()
        stats[key] = val
    return stats

def merge_and_add_stats(outputs_dp):
    l.info('merging and adding stats...')
    dirs = [d for d in os.listdir(outputs_dp) if os.path.isdir(os.path.join(outputs_dp, d)) and d.startswith('fuzzer')]
    dirs.sort()
    all_stats = dict()
    for d in dirs:
        ver = d.split('_')[-1]
        stats_fp = os.path.join(outputs_dp, d, 'fuzzer_stats')

        if not os.path.isfile(stats_fp):
            l.error('RaiseStats Exception: no such file {}'.format(stats_fp))
            continue

        stats = parse_stats(stats_fp)
        afl_banner = stats['afl_banner']

        #add stats

        pid = check_afl_on(afl_banner)
        stats['pid_on'] = pid

        if d.endswith('filter'):

            num_code_block = -1
            if g_code_block is not None:
                num_code_block = g_code_block.update()
            else:
                l.error('g_code_block undefined')            
            stats['num_code_block'] = num_code_block

        else:
            pass


        all_stats[ver] = stats

    return all_stats

def merge_stats_helper(all_stats):
    # stats = dict()
    pass


def check_code_blocks(afl_banner):
    pass

def check_afl_on(afl_banner):
    cmd = 'ps -ef|grep afl-fuzz|grep {}'.format(afl_banner)
    out = subprocess.check_output(cmd, shell=True)
    pid = -1
    for line in out.splitlines():
        if 'afl-fuzz' in line:
            pid = int(line.split(None)[1])
            break
    return pid
    



def do_raise(seq):
    its_stats_dir = os.path.join(g_stats_dir, g_task_name)
    all_stats_fp = os.path.join(its_stats_dir, 'all_fuzzer_stats_{:0>3}'.format(seq))
    all_stats = merge_and_add_stats(g_shared_outputs)
    all_stats.update(merge_and_add_stats(g_co_outputs))
    # with open(all_stats_fp, 'w+') as f:
    #     f.write(json.dumps(all_stats))
    atomic_write(all_stats_fp, json.dumps(all_stats))
    l.info('#{} raised...'.format(seq))


def do_loop_thread(stop_event):
    time.sleep(60)

    ensure_dir(g_stats_dir)
    its_stats_dir = os.path.join(g_stats_dir, g_task_name)
    ensure_dir(its_stats_dir)

    global g_code_block
    filter_output_dirname = 'fuzzer-{}_filter'.format(g_task_name)
    cb_dir = os.path.join(g_co_outputs, filter_output_dirname, 'queue')
    g_code_block = CodeBlock(cb_dir)

    seq = 0
    while (not stop_event.is_set()):
        try:            
            do_raise(seq)
            seq += 1
            stop_event.wait(g_stats_raise_sec)
        except KeyboardInterrupt:
            return
        except:
            l.error("Unexpected RaiseStats Error: {}".format(sys.exc_info()[:2]))
    l.warning('-> raise_stats terminates')
        # time.sleep(g_stats_raise_sec)
        # do_raise()



class CodeBlock():

    def __init__(self, cb_dir):
        self.cb_set = Set([])
        self.next_cb_id = 0
        if os.path.isdir(cb_dir):
            self.cb_dir = cb_dir
        else:
            l.error('cannot find {}'.format(cb_dir))


    def read(self, cb_filepath):
        cb_list = []
        if os.path.isfile(cb_filepath):
            with open(cb_filepath, 'r') as f:
                cb_list = f.readlines()
        return cb_list

    def parse(self, cb_list):
        cb_set = Set([])
        for b in cb_list:
            [start, end, cb_idx] = b.strip().split(',')
            # cb_addr_tuple = (int(start, 16), int(end, 16), int(cb_idx))
            cb_addr_tuple = (int(start, 16), int(cb_idx))
            cb_set.add(cb_addr_tuple)
        return cb_set

    def update(self):
        cb_dir = self.cb_dir
        cb_files = [f for f in os.listdir(cb_dir) if os.path.isfile(os.path.join(cb_dir, f)) and f.startswith('blocks,id')]
        cb_files.sort()
        for cb_fn in cb_files:
            cur_cb_id = int(cb_fn[10:18])
            if cur_cb_id < self.next_cb_id:
                continue
            cb_filepath = os.path.join(cb_dir, cb_fn)
            cb_list = self.read(cb_filepath)
            cb_set = self.parse(cb_list)
            self.cb_set = self.cb_set.union(cb_set)
            self.next_cb_id = cur_cb_id + 1
        return len(self.cb_set)


if __name__ == '__main__':
    do_raise()






