#!/usr/bin/python
#encoding: utf-8
import sys, os, subprocess, time, platform, ConfigParser, fcntl, thread, signal, re, getopt
import smtplib, sys, socket
from email.mime.text import MIMEText
import urllib2, time, copy

class ExitCheck:
    m_exit = False
    m_exit_callback = None
    m_exit_param = ()
    def __init__(self, exit_callback, *param):
        self.m_exit_callback = exit_callback
        self.m_exit_param = param
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    def signal_handler(self, signum, frame):
        if self.m_exit:
            log_error('process recv dumplicate exit request.')
            return
        self.m_exit = True
        log_info('process recv quit signal ... ')
        if self.m_exit_callback:
            self.m_exit_callback(*self.m_exit_param)
    def wait(self):
        while self.m_exit == False:
            time.sleep(1)
        log_info('process exit success.')

class Config:
    def __init__(self):
        self.save_log_size = 500*1024*1024
        self.log_dir = 'log'
        self.monitor_keyword_list = []
        self.monitor_newfile_list = []
        self.monitor_quit = False
        self.quit_restart = False
        self.restart_wait_sec = 10
        self.invalid_quit_mail_msg = 'Invalid Quit'
        '''mail option'''
        self.mail_host = 'smtp.163.com'
        self.mail_from_name = 'Founder Observer'
        self.mail_user = 'yyclyj858888'
        self.mail_psw = 'yyclyjyyclyj'
        self.mail_postfix = '163.com'
        self.mail_to_list = []

class ConfigManager:
    def __init__(self, config_file = '/etc/observer_config'):
        self.config_file = config_file
        self.cf = ConfigParser.ConfigParser()
        self.cf.read(config_file)
        self.listen_port = 9090
        if self.cf.has_option('common', 'listen_port'):
            self.listen_port = self.cf.getint('common', 'listen_port')
        self.work_process_num = 2
        '''
        if self.cf.has_option('common', 'work_process_num'):
            self.work_process_num = self.cf.getint('common', 'work_process_num')
        '''
        self.work_dir = '/var/observer'
        if self.cf.has_option('common', 'work_dir'):
            self.work_dir = self.cf.get('common', 'work_dir')
        self.record_file = 'process.dat'
        if self.cf.has_option('common', 'record_file'):
            self.record_file = self.cf.get('common', 'record_file')
        self.socket_timeout = 10
        if self.cf.has_option('common', 'socket_timeout_sec'):
            self.socket_timeout = self.cf.getint('common', 'socket_timeout_sec')
        self.service_log_file = 'service_log'
        if self.cf.has_option('common', 'service_log'):
            self.service_log_file = self.cf.get('common', 'service_log')
        self.mail_interval_sec = 60 
        if self.cf.has_option('common', 'mail_interval_sec'):
            self.mail_interval_sec = self.cf.getint('common', 'mail_interval_sec')
        self.select_timeout = 2
        if self.cf.has_option('common', 'select_timeout'):
            self.select_timeout = self.cf.getint('common', 'select_timeout')
        self.base_cfg = Config()
        self.__load_config('base', self.base_cfg)
    def __load_config(self, sec_name, config):
        if not self.cf.has_section(sec_name):
            return False
        if self.cf.has_option(sec_name, 'log_save_size'):
            config.save_log_size = self.cf.getint(sec_name, 'log_save_size')
        if self.cf.has_option(sec_name, 'log_dir'):
            config.log_dir = self.cf.get(sec_name, 'log_dir').strip('/')
        if self.cf.has_option(sec_name, 'monitor_keyword'):
            for item_val in self.cf.get(sec_name, 'monitor_keyword').split(';'):
                item_val = my_strip(item_val)
                if len(item_val) > 0:
                    config.monitor_keyword_list.append(item_val)
        if self.cf.has_option(sec_name, 'monitor_newfile'):
            for item_val in self.cf.get(sec_name, 'monitor_newfile').split(';'):
                item_val = my_strip(item_val)
                if len(item_val) > 0:
                    config.monitor_newfile_list.append(item_val)
        if self.cf.has_option(sec_name, 'monitor_quit'):
            config.monitor_quit = self.cf.getboolean(sec_name, 'monitor_quit')
        if self.cf.has_option(sec_name, 'quit_restart'):
            config.quit_restart = self.cf.getboolean(sec_name, 'quit_restart') 
        if self.cf.has_option('common', 'restart_wait_sec'):
            self.restart_wait_sec = self.cf.getint('common', 'restart_wait_sec')
        '''mail option'''
        if self.cf.has_option(sec_name, 'mail_from'):
            config.mail_from_name = self.cf.get(sec_name, 'mail_from')        
        if self.cf.has_option(sec_name, 'mail_server'):
            config.mail_host = self.cf.get(sec_name, 'mail_server')
        if self.cf.has_option(sec_name, 'mail_reporter'):
            config.mail_user = self.cf.get(sec_name, 'mail_reporter')
        if self.cf.has_option(sec_name, 'mail_reporter_password'):
            config.mail_psw  = self.cf.get(sec_name, 'mail_reporter_password')
        if self.cf.has_option(sec_name, 'mail_postfix'):
            config.mail_postfix = self.cf.get(sec_name, 'mail_postfix')
        if self.cf.has_option(sec_name, 'mail_to'):
            config.mail_to_list = self.cf.get(sec_name, 'mail_to')

        if self.cf.has_option(sec_name, 'mail_to'):
            for item in self.cf.get(sec_name, 'mail_to').split(';'):
                if item.find('@') <= 0:
                    log_error('skip invalid mail_to address: %s' % item)
                    continue
            item = item.strip('\n').strip('\r').strip(' ')
            config.mail_to_list.append(item)
        return True 
    def get_cmd_config(self, cmd_id):
        cmd_cfg = copy.deepcopy(self.base_cfg)
        self.__load_config(cmd_id, cmd_cfg)
        return cmd_cfg

def log_error(str):
    time_str = time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(time.time()))
    sys.stderr.write('[%s] [%x] [error] %s\n' % (time_str, thread.get_ident(), str))
    sys.stderr.flush()

def log_info(str):
    time_str = time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(time.time()))
    sys.stdout.write('[%s] [%x] [info] %s\n' % (time_str, thread.get_ident(), str))
    sys.stdout.flush()

def my_strip(str):
    white_space_lst = ['\n', '\r', '\t', ' ']
    res = ''
    beg = 0
    while beg < len(str):
        if str[beg] not in white_space_lst:
            break
        beg += 1
    end = len(str) - 1
    while end >= 0:
        if str[end] not in white_space_lst:
            break
        end -= 1
    if beg >= len(str) or end < 0 or beg > end:
        return ''
    return str[beg:end + 1]

def my_split(str, sep):
    result = []
    array = str.split(sep)
    for item in array:
        cur = my_strip(item)
        if len(cur) > 0:
            result.append(cur)
    return result

def get_platform():
    return platform.platform().strip(' ')

def process_exist(pid):
    platform_name = get_platform()
    if not platform_name.startswith('Linux'):
        return True
    status_file = '/proc/%s/status' % pid
    if not os.path.exists(status_file):
        return False
    lines = open(status_file, 'r').readlines()
    for line in lines:
        line = line.strip('\n')
        cols = line.split('\t')
        if len(cols) > 1 and cols[0] == 'State:':
            return cols[1] != 'Z (zombie)'
    return True

def kill_process(pid, sig_val):
    if pid <= 0:
        return
    try:
        os.kill(pid, sig_val)
    except Exception, err:
        pass

def init_log_file_name(log_dir, cmd_id):
    log_dir = log_dir.strip('/')
    return "%s/%s.std" % (log_dir, cmd_id), "%s/%s.err" % (log_dir, cmd_id)

def init_log_file(log_dir, cmd_id):
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    std_file_name, err_file_name = init_log_file_name(log_dir, cmd_id)
    std_file = open(std_file_name, 'a')
    err_file = open(err_file_name, 'a')
    return std_file, err_file

def log_file_name(log_dir, cmd_id):
    log_dir = log_dir.strip('/')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    time_str = time.strftime('%Y-%m-%d_%H', time.localtime(time.time()))
    std_file_name = '%s/%s_%s.std' % (log_dir, cmd_id, time_str)
    err_file_name = '%s/%s_%s.err' % (log_dir, cmd_id, time_str)
    return std_file_name, err_file_name 

'''create log file'''
def log_file(log_dir, cmd_id):
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    std_file_name, err_file_name = log_file_name(log_dir, cmd_id)
    std_file = open(std_file_name, 'a')
    err_file = open(err_file_name, 'a')
    return std_file, err_file  

'''obtain command id'''
def get_cmd_id(cmd_str):
    args = my_split(cmd_str, ' ')
    cmd_id = ''
    if args[0] not in ['python', 'sh', 'php']:
        cmd_id = args[0]
    elif len(args) > 1:
        cmd_id = args[1]
    cmd_id = os.path.splitext(os.path.split(cmd_id)[1])[0]
    return cmd_id

'''process command arguments, start from idx 0'''
def get_observer_cmd(argv):
    if len(argv) < 1:
        log_error("have no process argument")
        return None 
    process_cmd = ''
    for i in xrange(0, len(argv)):
        if argv[i] == 'nohup' or argv[i] == '&':
            log_error('skip argv[%d]' % i)
            continue
        if argv[i] == '>':
            log_error('skip log redirection')
            return '', ''
        if len(process_cmd) > 0:
            process_cmd += ' '
        process_cmd += argv[i]
    args = process_cmd.split(' ')
    if len(args[0]) > 3:
        if args[0][-3:] == '.sh':
            process_cmd = 'sh %s' % process_cmd
        if args[0][-3:] == '.py':
            process_cmd = 'python %s' % process_cmd
    return process_cmd

'''file_pattern should be regex pattern'''
def get_file_lst(file_pattern, directory, recursive = True):
    res  = []
    size = 0
    for parent,dirnames,filenames in os.walk(directory):
        for file_name in filenames:
            if re.match(file_pattern, file_name):
                file_path = parent+'/'+file_name
                res.append(file_path)
                size += os.path.getsize(file_path)
        if not recursive:
            break
    return res, size

def get_local_ip(ifname = 'eth0'): 
    import socket, fcntl, struct 
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) 
    inet = fcntl.ioctl(s.fileno(), 0x8915, struct.pack('256s', ifname[:15])) 
    return socket.inet_ntoa(inet[20:24]) 

def send_mail(to_list, sub, content, main_server, mail_user, mail_pass, mail_postfix, from_name):
    me = from_name + "<"+mail_user + "@" + mail_postfix + ">" 
    content += '\n\n*** This email is sent by robot, please do NOT reply. ***\n\n'
    msg = MIMEText(content)
    msg['Subject'] = sub 
    msg['From'] = me
    msg['To'] = ';'.join(to_list)
    log_info('start mail to %s ...' % str(to_list))
    try:
        s = smtplib.SMTP(timeout = 10)
        s.connect(main_server)
        s.login(mail_user,mail_pass)
        s.sendmail(me, to_list, msg.as_string())
        s.close()
        log_info('mail to %s success.' % str(to_list))
        return True
    except Exception, e:
        log_error("mail to %s exception: %s" % (str(to_list), e)) 
        return False

g_msg_end_flag = ';'
def client_send_and_recv(client_socket, send_cont):
    global g_msg_end_flag
    recv_content = ''
    try:
        client_socket.send(send_cont)
        while True:
            cur_content = client_socket.recv(4096)
            idx = cur_content.rfind(g_msg_end_flag)
            if idx >= 0:
                cur_content = cur_content[0:idx]
            recv_content += cur_content
            if idx >= 0:
                break
    except Exception, err:
        log_error('network exception: %s' % err)
    return recv_content

def handle_server_response(client_socket, recv_content):
    if len(recv_content) == 0:
        client_socket.close()
        sys.exit(1)
    cols = my_split(recv_content, ':')    
    if len(cols) == 0:
        log_error('invalid response: %s' % recv_content)
        sys.exit(1)
    if cols[0] == 'success':
        return True, ':'.join(cols[1:])
    elif cols[0] == 'fail':
        return False, ':'.join(cols[1:])
    else:
        log_error('invalid response flag: %s' % recv_content)
        sys.exit(1)

def client_start_cmd(client_socket, cmd_str):
    send_cont = 'start %s %s' % (os.getcwd(), cmd_str) 
    recv_content = client_send_and_recv(client_socket, send_cont)
    return handle_server_response(client_socket, recv_content) 

def client_stop_cmd(client_socket, pid, cmd_str):
    send_cont = 'stop %s' % pid
    if pid is None:
        send_cont = 'stop %s %s' % (os.getcwd(), cmd_str) 
    recv_content = client_send_and_recv(client_socket, send_cont)
    return handle_server_response(client_socket, recv_content)

def client_cmd_status(client_socket, pid, cmd_str):
    send_cont = 'pstatus %s' % pid
    if pid is None:
        send_cont = 'pstatus %s %s' % (os.getcwd(), cmd_str) 
    recv_content = client_send_and_recv(client_socket, send_cont)
    return handle_server_response(client_socket, recv_content)

def obtain_client_socket_cmd_name():
    socket.setdefaulttimeout(10)
    cfg_manager = ConfigManager()
    opts, args = getopt.getopt(sys.argv[1:], "h:p:")
    dst_ip   = '127.0.0.1'
    dst_port = cfg_manager.listen_port 
    for op, value in opts:
        if op == '-h':
            dst_ip = value
        elif op == '-p':
            dst_port = int(value)
    cmd_str  = get_observer_cmd(args)
    if cmd_str is None:
        sys.exit(1)
    client_socket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    client_socket.connect((dst_ip, dst_port))
    return client_socket, cmd_str
