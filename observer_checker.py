#encoding: utf-8
import os
import signal
import select, sys, subprocess, Queue
from observer_common import *

'''检查器基类'''
class Checker:
    '''返回True就触发报警'''
    def check(self, buffer):
        return False
    def checker_subject(self):
        return "CHECK"
    def checker_msg(self):
        return "check message"

'''关键词检查器'''
class KeywordChecker(Checker):
    ''' keyword:10/60 表示在60秒内如果keyword出现了10次就触发'''
    ''' keyword       表示只要出现就触发'''
    def __init__(self, init_val):
        sep = init_val.find(':')
        self.m_word  = ''
        self.m_max_times = 0
        self.m_cur_times = 0
        self.m_interval_sec = 0
        self.m_check_time = time.time()
        self.m_triggered = False
        if sep <= 0:
            self.m_word = init_val 
            return
        self.m_word = init_val[0:sep]
        other_str = init_val[sep+1:]
        sep = other_str.find('/')
        if sep <= 0:
            return
        self.m_max_times = int(other_str[0:sep])
        other_str = other_str[sep+1:]
        self.m_interval_sec = int(other_str)
    def check(self, buffer):
        if buffer.find(self.m_word) >= 0:
            self.m_cur_times += 1
        if not self.m_triggered and self.m_cur_times > self.m_max_times:
            log_error('KeywordChecker triggered')
            self.m_triggered = True
            return True
        cur_time = time.time()
        if cur_time > self.m_check_time + self.m_interval_sec:
            self.m_cur_times = 0
            self.m_triggered = False
            self.m_check_time = cur_time
        return False
    def checker_subject(self):
        return "KeywordChecker"
    def checker_msg(self):
        return "KeywordChecker %s occured %d times." % (self.m_word, self.m_max_times)

'''文件更新检查器'''
class NewFileChecker(Checker):
    '''/home/data/:.*\.txt:2/60   在/home/data/目录下，文件*.txt，60秒内少于2个文件更新就报警'''
    def __init__(self, init_val):
        cols = init_val.split(':')
        assert(len(cols) == 3)
        self.m_directory = cols[0]
        self.m_pattern = cols[1]
        other_cols = cols[2].split('/')
        assert(len(other_cols) == 2)
        self.m_min_file_cnt = int(other_cols[0])
        self.m_interval_sec = int(other_cols[1])
        self.m_check_time = 0
    def check(self, buffer):
        cur_time = time.time()
        if self.m_check_time + self.m_interval_sec > cur_time:
            return False
        file_lst, file_size = get_file_lst(self.m_pattern, self.m_directory, False)
        cnt = 0
        for file in file_lst:
            modify_time = os.path.getmtime(file)
            if modify_time + self.m_interval_sec > cur_time:
                cnt += 1
        self.m_check_time = cur_time
        ret = cnt < self.m_min_file_cnt
        if ret:
            log_info('NewFileChecker triggered.')
        return ret 
    def checker_subject(self):
        return "NewFileChecker"
    def checker_msg(self):
        return "NewFileChecker %s new files < %d." % (self.m_directory, self.m_min_file_cnt)

'''日志文件大小检查器'''
class LogSizeChecker(Checker):
    def __init__(self, directory, file_pattern, max_log_size):
        self.m_cur_size = 0
        self.m_directory = directory
        self.m_file_pattern = file_pattern
        self.m_max_size = max_log_size
        self.m_err_msg = ''
        file_lst, self.m_cur_size = get_file_lst(self.m_file_pattern, self.m_directory, False)
    def check(self, buffer):
        self.m_cur_size += len(buffer)
        '''考虑到内存到磁盘可能有4096的缓冲区大小'''
        if self.m_cur_size < self.m_max_size + 4096:
            return False
        file_lst, file_size = get_file_lst(self.m_file_pattern, self.m_directory, False)
        '''文件数目过少, 避免重复探测'''
        if len(file_lst) <= 2:
            self.m_cur_size = 0
            return False
        file_lst.sort() 
        while file_size > self.m_max_size and len(file_lst) > 2:
            try:
                file_size -= os.path.getsize(file_lst[0])
                os.remove(file_lst[0])
                log_info('removed log file %s' % file_lst[0]) 
                del(file_lst[0])
            except Exception, err:
                self.m_err_msg = err
                log_error('LogSizeChecker triggered: %s' % err)
                return True
        self.m_cur_size = file_size;
        return False
    def checker_subject(self):
        return "LogSizeChecker"
    def checker_msg(self):
        return "LogSizeChecker remove file error: %s" % self.m_err_msg

'''进程退出检测器'''
'''
class InvalidQuitChecker(Checker):
    def __init__(self, pid, quit_check_interval):
        self.m_check_interval = quit_check_interval
        self.m_check_time = 0
    def check(self, buffer):
        cur_time = time.time()
        if self.m_check_time + self.m_check_interval > cur_time:
            return False
        self.m_check_time = cur_time
        return not process_exist(pid)
    def checker_subject(self):
        return "InvalidQuitChecker"
    def checker_msg(self):
        return "InvalidQuitChecker"
'''
