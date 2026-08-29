"""Build the separate DEVELOPMENT CALIBRATION ONLY set from source evidence."""
import hashlib, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'calibration/calibration_v1.json'
ANS=[
('设备柜只给 A100 V1 左右各留 6 厘米，散热空间合规吗？','EVAL-A100-V1','A100V1-POWER'),
('A100 V2 想走证书接入办公网，证书里必须带什么设备信息？','EVAL-A100-V2','A100V2-NET'),
('A100 V2 进入恢复菜单以后，怎样才会真正擦除配置？','EVAL-A100-V2','A100V2-RESET'),
('A200 机柜进风达到 36℃ 时是否符合安装要求？','EVAL-A200','A200-POWER'),
('A200 的第二块屏幕需要兼容哪个 HDCP 版本？','EVAL-A200','A200-CAPACITY'),
('M20 级联链路做到了 40 米，文档要求增加什么模块？','EVAL-A200','A200-AUDIO'),
('会议运营员能不能调整网络设置并导出全量审计日志？','EVAL-ACCOUNT','ACC-ROLES'),
('员工离职后，其自动化任务最迟何时应完成移交？','EVAL-ACCOUNT','ACC-OFFBOARD'),
('站点管理员能导出整个组织的完整成员名单吗？','EVAL-ACCOUNT','ACC-EXPORT'),
('访客无线和会议终端可以放在同一个二层广播域吗？','EVAL-DEPLOY','DEPLOY-VLAN'),
('如果出口设备改写了媒体 DSCP，应该在哪一侧重新标记？','EVAL-DEPLOY','DEPLOY-QOS'),
('验收测试是否必须包含断网后的重连？','EVAL-DEPLOY','DEPLOY-ACCEPTANCE'),
('终端已注册但双向没有声音画面，应检查哪段 UDP 范围？','EVAL-NETWORK','NET-NO-MEDIA'),
('无线同信道利用率到 75% 时，手册建议先加大发射功率吗？','EVAL-NETWORK','NET-WIFI'),
('三个会议室同时中断且没有绕行方案，在运维分级里算什么？','EVAL-OPS','OPS-SEVERITY'),
('普通故障工单里的公网 IP 和邮箱应怎样处理？','EVAL-SECURITY','SEC-REDACT'),
('会议共享屏幕截图在数据分类中属于哪一级？','EVAL-SECURITY','SEC-CLASS'),
('A100 V2 顶部的散热孔可以被装饰面板盖住吗？','EVAL-A100-V2','A100V2-POWER'),
('设备因错误电压适配器损坏，能否免费保修？','EVAL-WARRANTY','WAR-EXCLUDE'),
('把设备直接寄到维修中心但没有 RMA 编号，会被接收吗？','EVAL-WARRANTY','WAR-RMA'),
]
NEG=[
'A100 V2 摄像头支持多少倍光学变焦？','A200 是否内置锂电池以及续航多久？','公司为每个会议室提供多少云存储配额？','S2 服务事件保证几小时内彻底修复？','会议模板是否支持与 Salesforce 自动同步？','A100 V1 的蓝牙芯片生产厂商是谁？','设备是否支持日语语音唤醒？','维修中心位于哪个城市？','A200 主机的噪声分贝是多少？','企业账号密码最少必须包含几个特殊字符？','日志导出压缩包默认密码是什么？','会议录制是否支持自动生成英文字幕？','A100 V2 的摄像头水平视场角是多少度？','哪家运营商被公司指定为会议专线供应商？','设备采购超过多少台可以获得折扣？','P2 事件必须在几天内提交根因报告？','云端高级录制服务的年度价格是多少？','公司是否允许把会议数据备份到个人 Dropbox？','A200 的 HDMI 线最长允许多少米？','终端固件下一次发布时间是哪一天？']
def main():
 cases=[]
 for i,(q,d,l) in enumerate(ANS,1): cases.append({'query_id':f'cal{i:03d}','query':q,'category':'calibration_answerable','tags':['development_calibration'],'answerable':True,'relevant_documents':[d],'relevant_locators':[l]})
 for i,q in enumerate(NEG,21): cases.append({'query_id':f'cal{i:03d}','query':q,'category':'calibration_no_answer','tags':['development_calibration','no_answer'],'answerable':False,'relevant_documents':[],'relevant_locators':[]})
 data={'status':'DEVELOPMENT CALIBRATION ONLY','purpose':'Evidence Gate calibration; not benchmark or resume metric','separation':'Never use Frozen Test outcomes to tune this set or its rule','cases':cases}
 OUT.parent.mkdir(parents=True,exist_ok=True); payload=json.dumps(data,ensure_ascii=False,indent=2)+'\n'; OUT.write_text(payload,encoding='utf-8'); print(json.dumps({'path':str(OUT),'count':len(cases),'answerable':20,'no_answer':20,'sha256':hashlib.sha256(payload.encode()).hexdigest()},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
