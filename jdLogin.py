# coding=utf-8
from selenium import webdriver
import selenium.webdriver.support.ui as ui
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import json
import random
import execjs
import requests
import time
from lxml import etree
import sys
reload(sys)
sys.setdefaultencoding('utf-8')
import logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
                    datefmt='%a, %d %b %Y %H:%M:%S',
                    filename='./spider.log',
                    filemode='a')


class JdSpider(object):
    """京东火车票"""

    def __init__(self, data_dic):
        super(JdSpider, self).__init__()
        self.arg = data_dic
        self.JDSession = requests.session()
        self.JDSession.header = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64)AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.87 Safari/537.36',
            'Connection': 'keep-alive',
        }
        # self.JDSession.proxies =  random.choice(proxies)

    @staticmethod
    def response_status(resp):
        if resp.status_code != requests.codes.OK:
            print 'Status: %u, Url: %s' % (resp.status_code, resp.url)
            return False
        return True

    def need_auth_code(self):
        # check if need auth code
        auth = 'https://passport.jd.com/uc/showAuthCode'
        auth_dat = {
            'loginName': self.arg.get("channalName"),
        }

        payload = {
            'r': random.random(),
            'version': 2015
        }

        resp = self.JDSession.post(auth, data=auth_dat, params=payload)
        logging.info(resp.content)
        if self.response_status(resp):
            js = json.loads(resp.text[1:-1])
            return js['verifycode']
        return False

    def PhantomJSAndRequests(self):
        """phantomJS get auth code"""
        jdName = self.arg.get("channalName")
        self.JDSession = requests.session()
        home = "https://passport.jd.com/uc/login?ltype=logout"
        try:
            self.driver.get(home)
            html = etree.HTML(self.driver.page_source)
            wait = ui.WebDriverWait(self.driver, 5, 0.5)
            login_element = wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//div[@class='login-tab login-tab-r']")))
            login_element.click()
            wait.until(lambda dr: dr.find_element_by_xpath(
                "//div[@style='display: block; visibility: visible;']").is_displayed())
            username_element = self.driver.find_element_by_xpath(
                "//div[@class='item item-fore1']/input[@id='loginname']")
            userpassword_element = self.driver.find_element_by_xpath(
                "//div[@id='entry']/input[@id='nloginpwd']")
            username_element.send_keys(jdName)
            userpassword_element.click()
            imgelement = wait.until(EC.visibility_of_element_located(
                (By.XPATH, "//div[@id='o-authcode'][@style='display: block;']/img")))
            location = imgelement.location  # 获取验证码x,y轴坐标
            size = imgelement.size  # 获取验证码的长宽
            rangle = (int(location['x']), int(location['y']), int(location[
                      'x'] + size['width']), int(location['y'] + size['height']))  # 写成我们需要截取的位置坐标

            imgname = self.fileName(stance="Code", flag=jdName)
            # time.sleep(1)
            self.driver.save_screenshot(imgname)
            CodeImgname = imgname[:-4] + "code" + imgname[-4:]

            i = Image.open(imgname)  # 打开截图
            frame4 = i.crop(rangle)  # 使用Image的crop函数，从截图中再次截取我们需要的函数
            frame4.save(CodeImgname)
            code = raw_input("please input auth code:")  # 实际开发环境中使用打码平台
            token = html.xpath('//input[@id="token"]/@value')[0]
            uuid = html.xpath('//input[@id="uuid"]/@value')[0]

            for cookie in self.driver.get_cookies():
                if cookie["name"] in {"qr_t", "alc", token}:  # 不解释
                    self.JDSession.cookies[
                        str(cookie['name'])] = str(cookie['value'])
            return {"uuid": uuid, "_t": token, "authcode": code}
        except Exception as e:
            print e
            return False

    def login(self):
        jdName = self.arg.get("channalName")
        jdPwd = self.arg.get("channalPwd")
        url = "https://passport.jd.com/uc/login?ltype=logout"
        post_url = "https://passport.jd.com/uc/loginService"

        rt = self.JDSession.get(url)
        html = etree.HTML(rt.text)

        data = dict()
        # for e in html.cssselect("form input"):
        #     data[e.get('name')] = e.get("value")
        for e in html.xpath("//form/input"):
            data[e.xpath("./@name")[0]] = e.xpath("./@value")[0]

        if not data.get("pubKey"):  # 发现过一次pubKey不在表单内
            data['pubKey'] = html.xpath("//input[@name='pubKey']/@value")[0]

        with open('jd_login.js', 'r') as f:
            source = f.read()
        phantom = execjs.get('PhantomJS')
        getpass = phantom.compile(source)
        nloginpwd = getpass.call('get', data['pubKey'], jdPwd)

        data["loginname"] = jdName
        data['nloginpwd'] = nloginpwd

        self.judgment = self.need_auth_code()  # 判断是否需要验证码

        if self.judgment:
            self.driver = webdriver.PhantomJS()
        else:
            time.sleep(2)  # 必须得有延迟

        if self.judgment:
            newDic = self.PhantomJSAndRequests()
            if not newDic:
                return False
            data.update(newDic)

        payload = {
            'r': random.random(),
            'uuid': data['uuid'],
            'version': 2015,
        }

        response = self.JDSession.post(post_url, data=data)
        print response.content
        try:
            result = json.loads(response.content[1:-1])
        except Exception as e:
            logging.error(e)
            return False
        if result.get("success"):
            self.cookies = self.JDSession.cookies.get_dict(".jd.com")
            return {"status": True}
        elif result.get("pwd"):
            return {"status": False, "message": result.get("pwd"), "code": 12}
        elif result.get("username"):
            return {"status": False, "message": result.get("username"), "code": 12}
        elif self.judgment and result.get("emptyAuthcode"):  # 验证码识别错误重发
            return {"status": False, "message": result.get("emptyAuthcode"), "code": 10}
        else:
            return {"status": False, "message": response.content, "code": 10}

if __name__ == '__main__':
    data_dic = dict(channalName="18356303053", channalPwd="chao11305623")
    jd = JdSpider(data_dic)
    rst = jd.login()
    print rst
