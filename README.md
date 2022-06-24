# 浙江大学自动健康打卡

## 使用方法

建议在服务器上挂着，环境为python3。运行步骤：

1. 下载本脚本：git clone https://github.com/wujeevan/autohitcard.git
2. 填写config.json内容，因为使用qq邮箱通知打卡失败，所以需申请qq邮箱imap服务密码，方法见[百度经验](https://zhidao.baidu.com/question/2058074561101447467.html "点击链接")
3. 安装依赖包：pip install -r requirements.txt
4. 后台运行：nohup python hitcard.py </dev/null >run.log 2>&1 &

## 感谢

感谢贡献者@Tishacy 
