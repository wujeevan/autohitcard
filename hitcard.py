# -*- coding: utf-8 -*-
import requests
import json
import re
import time
import datetime
import os
import random
from halo import Halo
from apscheduler.schedulers.blocking import BlockingScheduler
import smtplib
from email.mime.text import MIMEText
import ddddocr


ocr = ddddocr.DdddOcr(show_ad=False)
configs = json.loads(open('config.json', 'r').read())
username = configs["username"]
password = configs["password"]
hour = configs["schedule"]["hour"]
minute = configs["schedule"]["minute"]
delay = configs["schedule"]["delay"] #最大延迟delay hours内随机时间打卡
mail_host = "smtp.qq.com"
mail_port = 465
mail_user = configs['mailuser']
mail_pass = configs['mailpass'] #需申请QQ邮箱smtp/pop服务的专用登录密码
sender = "me <{}>".format(mail_user)
receivers = [mail_user]


def sendmail(
    title="",
    content="",
    mail_host=mail_host,
    mail_port=mail_port,
    mail_user=mail_user,
    mail_pass=mail_pass,
    sender=sender,
    receivers=receivers,
    text_type="plain",
    SSL=True
):
    message = MIMEText(content, text_type, "utf8")
    message["From"] = sender
    message["To"] = ",".join(receivers)
    message["Subject"] = title
    if SSL:
        smtpObj = smtplib.SMTP_SSL(mail_host, mail_port)
    else:
        smtpObj = smtplib.SMTP(mail_host, mail_port)
    smtpObj.login(mail_user, mail_pass)
    smtpObj.sendmail(mail_user, receivers, message.as_string())


class HitCarder(object):
    """Hit carder class

    Attributes:
        username: (str) 浙大统一认证平台用户名（一般为学号）
        password: (str) 浙大统一认证平台密码
        login_url: (str) 登录url
        base_url: (str) 打卡首页url
        save_url: (str) 提交打卡url
        self.headers: (dir) 请求头
        sess: (requests.Session) 统一的session
    """

    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.login_url = "https://zjuam.zju.edu.cn/cas/login?service=https%3A%2F%2Fhealthreport.zju.edu.cn%2Fa_zju%2Fapi%2Fsso%2Findex%3Fredirect%3Dhttps%253A%252F%252Fhealthreport.zju.edu.cn%252Fncov%252Fwap%252Fdefault%252Findex"
        self.base_url = "https://healthreport.zju.edu.cn/ncov/wap/default/index"
        self.save_url = "https://healthreport.zju.edu.cn/ncov/wap/default/save"
        self.code_url = "https://healthreport.zju.edu.cn/ncov/wap/default/code"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36"
        }
        self.sess = requests.Session()

    def login(self):
        """Login to ZJU platform."""
        res = self.sess.get(self.login_url, headers=self.headers)
        execution = re.search('name="execution" value="(.*?)"', res.text).group(1)
        res = self.sess.get(url='https://zjuam.zju.edu.cn/cas/v2/getPubKey', headers=self.headers).json()
        n, e = res['modulus'], res['exponent']
        encrypt_password = self._rsa_encrypt(self.password, e, n)

        data = {
            'username': self.username,
            'password': encrypt_password,
            'execution': execution,
            '_eventId': 'submit'
        }
        res = self.sess.post(url=self.login_url, data=data, headers=self.headers)

        # check if login successfully
        if '统一身份认证' in res.content.decode():
            raise LoginError('登录失败，请核实账号密码重新登录')
        return self.sess

    def post(self):
        """Post the hit card info."""
        res = self.sess.post(self.save_url, data=self.info, headers=self.headers)
        return json.loads(res.text)

    def get_date(self):
        """Get current date."""
        today = datetime.date.today()
        return "%4d%02d%02d" % (today.year, today.month, today.day)

    def get_info(self, html=None):
        """Get hit card info, which is the old info with updated new time."""
        if not html:
            res = self.sess.get(self.base_url, headers=self.headers)
            code_bytes = self.sess.get(self.code_url, headers=self.headers).content
            html = res.content.decode()
        try:
            old_infos = re.findall(r'oldInfo: ({[^\n]+})', html)
            old_infos = old_infos if len(old_infos) != 0 else re.findall(r'def = ({[^\n]+})', html)
            if len(old_infos) != 0:
                old_info = json.loads(old_infos[0])
            else:
                raise RegexMatchError("未发现缓存信息，请先至少手动成功打卡一次再运行脚本")
            new_info_tmp = json.loads(re.findall(r'def = ({[^\n]+})', html)[0])
            new_id = new_info_tmp['id']
            name = re.findall(r'realname: "([^\"]+)",', html)[0]
            number = re.findall(r"number: '([^\']+)',", html)[0]
        except IndexError as err:
            raise RegexMatchError('Relative info not found in html with regex: ' + str(err))
        except json.decoder.JSONDecodeError as err:
            raise DecodeError('JSON decode error: ' + str(err))

        
        new_info = old_info.copy()
        new_info['verifyCode'] = ocr.classification(code_bytes)
        # print(new_info['verifyCode'])
        # with open('code.png', 'wb') as f:
        #     f.write(code_bytes)
        new_info['id'] = new_id
        new_info['name'] = name
        new_info['number'] = number
        new_info["date"] = self.get_date()
        new_info["created"] = round(time.time())
        # form change
        new_info['jrdqtlqk[]'] = 0
        new_info['jrdqjcqk[]'] = 0
        new_info['sfsqhzjkk'] = 1  # 是否申领杭州健康码
        new_info['sqhzjkkys'] = 1  # 杭州健康吗颜色，1:绿色 2:红色 3:黄色
        new_info['sfqrxxss'] = 1  # 是否确认信息属实
        new_info['jcqzrq'] = ""
        new_info['gwszdd'] = ""
        new_info['szgjcs'] = ""
        self.info = new_info
        return new_info

    def _rsa_encrypt(self, password_str, e_str, M_str):
        password_bytes = bytes(password_str, 'ascii')
        password_int = int.from_bytes(password_bytes, 'big')
        e_int = int(e_str, 16)
        M_int = int(M_str, 16)
        result_int = pow(password_int, e_int, M_int)
        return hex(result_int)[2:].rjust(128, '0')


# Exceptions
class LoginError(Exception):
    """Login Exception"""
    pass


class RegexMatchError(Exception):
    """Regex Matching Exception"""
    pass


class DecodeError(Exception):
    """JSON Decode Exception"""
    pass


def main(username, password, delay=4):
    """Hit card process

    Arguments:
        username: (str) 浙大统一认证平台用户名（一般为学号）
        password: (str) 浙大统一认证平台密码
    """
    print("\n[Base Time] %s" % datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    # Add random delay
    sleep_time = random.randint(0, 3600 * int(delay))  # delay time(hour)
    # time.sleep(sleep_time)
    print('Delay for {}s'.format(sleep_time))
    time.sleep(sleep_time)
#     for i in tqdm(range(sleep_time)):
#         time.sleep(1)

    print("[Start Time] %s" % datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    print("🚌 打卡任务启动")
    spinner = Halo(text='Loading', spinner='dots')
    spinner.start('正在新建打卡实例...')
    hit_carder = HitCarder(username, password)
    spinner.succeed('已新建打卡实例')

    spinner.start(text='登录到浙大统一身份认证平台...')
    try:
        hit_carder.login()
        spinner.succeed('已登录到浙大统一身份认证平台')
    except Exception as err:
        spinner.fail(str(err))
        title = "打卡失败通知({})".format(time.strftime("%m-%d %H:%M", time.localtime()))
        content = '统一身份认证失败： ' + str(err)
        sendmail(title=title, content=content)
        return

    spinner.start(text='正在获取个人信息...')
    try:
        hit_carder.get_info()
        spinner.succeed('%s %s同学, 你好~' % (hit_carder.info['number'], hit_carder.info['name']))
    except Exception as err:
        spinner.fail('获取信息失败，请手动打卡，更多信息: ' + str(err))
        title = "打卡失败通知({})".format(time.strftime("%m-%d %H:%M", time.localtime()))
        content = '获取信息失败，请手动打卡，更多信息: ' + str(err)
        sendmail(title=title, content=content)
        return

    spinner.start(text='正在为您打卡...')
    try:
        res = hit_carder.post()
        if str(res['e']) == '0':
            spinner.stop_and_persist(symbol='🦄 '.encode('utf-8'), text='已为您打卡成功！')
        elif res['m'] == '验证码错误':
            # 重试10次验证码，确保通过验证
            max_retry, now = 10, 0
            while now < max_retry and res['m'] == '验证码错误':
                now += 1
                hit_carder.get_info()
                res = hit_carder.post()
            if now == max_retry:
                raise Exception("验证码识别失败")
            if str(res['e']) == '0':
                spinner.stop_and_persist(symbol='🦄 '.encode('utf-8'), text='已为您打卡成功！')
            else:
                spinner.stop_and_persist(symbol='🦄 '.encode('utf-8'), text=res['m'])
        else:
            spinner.stop_and_persist(symbol='🦄 '.encode('utf-8'), text=res['m'])
    except Exception as err:
        spinner.fail('数据提交失败 ' + str(err))
        title = "打卡失败通知({})".format(time.strftime("%m-%d %H:%M", time.localtime()))
        content = '数据提交失败：' + str(err)
        sendmail(title=title, content=content)
        return


if __name__ == "__main__":
    main(username, password, delay)

    # Schedule task
    scheduler = BlockingScheduler()
    scheduler.add_job(main, 'cron', args=[username, password], hour=hour, minute=minute)
    print('⏰ 已启动定时程序，每天 %02d:%02d 为您打卡' % (int(hour), int(minute)))
    print('Press Ctrl+{0} to exit'.format('Break' if os.name == 'nt' else 'C'))

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass
