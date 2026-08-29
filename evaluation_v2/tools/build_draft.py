"""Build the synthetic Evaluation V2 draft from source-authored documents/cases.

This builder is intentionally independent from production retrieval. It imports no
embedding, Milvus, RRF, rerank, or query workflow code. Relevant locators are
selected directly from the Markdown sources authored below.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC_DIR = ROOT / "documents"
DATASET_PATH = ROOT / "dataset" / "dataset_v2_draft.json"
MANIFEST_PATH = ROOT / "artifacts" / "manifest_draft.json"
CREATED_AT = "2026-08-29T00:00:00Z"
CONTEXT_MARKER = "<!-- synthetic-section-context -->"

NOTICE = "> **SYNTHETIC / FOR EVALUATION ONLY — NOT REAL COMPANY DATA**\n"

# Real enterprise manuals repeat governance and verification language across
# sections. These document-type-specific paragraphs make each source section a
# realistic retrieval unit (>500 characters with its authored facts) and create
# intentional same-document interference without adding answers for the queries.
SECTION_CONTEXT = {
    "user_manual": """执行本节操作前，管理员应核对设备铭牌、硬件代号与当前系统版本，并在变更记录中写明会议室、设备序列号和执行时间。界面名称相似并不代表不同型号可以共用参数；若屏幕显示项与本手册不一致，应停止操作并查阅对应版本，而不是尝试导入其他型号的配置。完成操作后，需要进行一次呼入、一次呼出和一次共享测试，并观察状态灯与管理门户事件。涉及复位、升级或存储介质的操作还应先备份必要数据。故障工单应记录实际现象和已执行步骤，不得只填写错误码，也不得根据其他型号的经验推测本机结论。""",
    "deployment_guide": """规划结果应经过网络、终端和安全负责人共同复核，并保存站点拓扑、地址规划、策略变更单和验收记录。测试应覆盖正常链路与至少一种故障场景，不能只依赖管理门户中的在线标记。多个会议室批量上线时，先选择一个非关键房间试点，确认媒体、共享和日志链路后再扩展。若现网设备会修改标记、代理流量或缩短会话，应记录实际策略而不是沿用默认假设。容量数字用于规划预留，不代表运营商账单、存储费用或服务等级承诺。""",
    "troubleshooting": """排障遵循从现象、链路到配置的顺序：先保存时间、会议标识和终端日志，再用可重复测试缩小范围。相似错误码可能来自完全不同的阶段，不能只凭编号替换硬件或恢复出厂。每次只改变一个条件，并记录改变前后的结果；如果问题无法稳定复现，应保留现场网络与时钟信息。恢复服务后仍需进行呼叫、媒体和重连验证。手册给出的首查项不是对根因的自动判定，遇到证据冲突时应升级人工分析。""",
    "policy": """本政策中的期限从明确写出的起点计算，工作日与自然日不得互换。申请人应保留购买、签收、授权和沟通记录；服务等级描述的是响应目标，不自动构成修复时限或换新承诺。不同附件和主机可能适用不同期限，提交申请时必须逐项核对序列号。未被政策明确列出的费用、运输方式或补偿标准不能由客服自行推断。发生争议时应记录事实并交由授权人员审核，不得为了快速结单修改故障日期或设备状态。""",
    "governance": """权限变更应遵循最小授权原则，通过受控账号执行并留下工单或审批记录。管理员需要核对操作对象属于组织、站点还是单个会议，避免把相似名称的角色当作同一权限。高风险导出、密钥和离职操作应由不同职责人员复核。完成变更后，要用只读方式确认权限结果，并检查审计日志是否记录操作者、目标与时间。规范未授权的数据范围不得通过临时共享账号绕过，文档没有规定的业务审批也不能自行补充。""",
    "security_policy": """处理数据前应先确认数据类别、业务目的和最小必要范围。保留期、恢复窗口与下载有效期是不同概念，不得相互替代。导出或上传材料时需要检查接收人、访问范围和到期时间，并保留审批依据。一般运维人员不应因为排障便利扩大敏感数据暴露。若现有文档没有规定某种加密方式、密码或例外期限，应标记为待确认，而不是从相邻条款推断。安全调查中的例外必须有明确批准人、原因和结束条件。""",
    "faq": """FAQ 用于快速澄清常见误解，不能替代型号手册、部署指南或安全政策。回答前先确认用户所说的是设备型号、系统版本还是管理门户功能；同一个词在这些范围内可能含义不同。若问题涉及具体端口、期限、保修或权限，应回到对应正式文档核对。FAQ 没有提到的型号、价格、根因或服务承诺均视为未知。建议用户在操作前保存当前配置，操作后执行最小验证，并把实际错误信息附在工单中。""",
    "operations_runbook": """值班人员应以时间线记录告警、用户影响、已采取措施和验证结果。优先级用于组织响应，不等于售后服务级别，也不能代替根因结论。批量操作前先建立回退点并保留故障样机，任何会清除数据的动作都需要事件指挥批准。证据应覆盖故障发生前后的窗口，上传前按数据安全规范处理。服务恢复只是进入观察阶段，关闭事件仍需确认影响范围、长期行动项和负责人。无法从证据确定的内容必须标记待人工分析。""",
}

DOCUMENTS = {
"EVAL-A100-V1": ("智能会议终端 A100 用户手册", "1.0", "user_manual", r"""
# 智能会议终端 A100 用户手册 V1

本手册适用于硬件代号 A100-G1、系统 1.8.x。后续版本的菜单和容量可能不同。

<!-- locator: A100V1-POWER -->
## 1 安装与供电

A100 V1 使用 12 V/3 A 圆口适配器。通电后状态灯先呈白色约 40 秒，完成启动后转为绿色。安装时应在设备两侧各保留至少 8 cm 散热空间，不得放入封闭抽屉。

<!-- locator: A100V1-NET -->
## 2 网络接入

有线网络只支持 100 Mbps 以太网；无线支持 2.4 GHz 和 5 GHz Wi-Fi 5。首次配置入口为“设置 > 网络 > 接入向导”。办公网采用 802.1X 时，V1 只支持 PEAP-MSCHAPv2。

<!-- locator: A100V1-PAIR -->
### 2.1 配对

管理员在终端输入六位配对码，配对码有效期 10 分钟。连续输入错误 5 次后，配对入口暂停 15 分钟，但设备本身不会退出已加入的会议。

<!-- locator: A100V1-MEETING -->
## 3 会议能力

A100 V1 单场会议最多显示 9 路视频画面，可保存 20 个常用会议室。V1 不支持本地 4K 录制；云端录制能力取决于企业订阅。

<!-- locator: A100V1-RESET -->
## 4 恢复与复位

短按复位孔仅重启设备。持续按住 12 秒并在红灯闪烁后松开，才会恢复出厂设置；本地网络、配对关系和自定义布局都会被清除。

<!-- locator: A100V1-UPDATE -->
## 5 软件更新

V1 的升级包必须使用 `.a1u` 格式，通过“维护 > 本地升级”导入。升级过程中不得断电；失败代码 U103 表示升级包签名不适用于 A100-G1。
"""),

"EVAL-A100-V2": ("智能会议终端 A100 用户手册", "2.0", "user_manual", r"""
# 智能会议终端 A100 用户手册 V2

本手册适用于硬件代号 A100-G2、系统 2.4.x。文中的 V2 规则不得用于 A100-G1。

<!-- locator: A100V2-POWER -->
## 1 安装与供电

A100 V2 使用 USB-C PD 45 W 供电。正常启动约需 25 秒，指示灯由紫色呼吸转为绿色常亮。设备两侧各保留 5 cm 即可，但顶部散热孔不得覆盖。

<!-- locator: A100V2-NET -->
## 2 网络接入

有线网络支持 1 Gbps；无线支持 Wi-Fi 6。接入入口调整为“系统设置 > 连接 > 网络配置”。802.1X 支持 PEAP-MSCHAPv2 与 EAP-TLS，EAP-TLS 客户端证书必须包含设备序列号。

<!-- locator: A100V2-PAIR -->
### 2.1 配对

六位配对码有效期缩短为 5 分钟。连续输入错误 3 次后，当前管理员账号锁定 20 分钟；其他已授权管理员仍可登录。

<!-- locator: A100V2-MEETING -->
## 3 会议能力

A100 V2 单场会议最多显示 16 路视频画面，可保存 50 个常用会议室。在插入通过兼容性认证的 USB 3.0 存储设备后，可启用本地 4K 录制。

<!-- locator: A100V2-RESET -->
## 4 恢复与复位

按住复位键 8 秒会进入恢复菜单，不会立即清空数据。只有在恢复菜单二次确认“擦除并恢复”后才执行出厂恢复。管理员可选择保留网络证书。

<!-- locator: A100V2-UPDATE -->
## 5 软件更新

V2 使用 `.a2u` 升级包，并支持 HTTPS 在线升级。错误 U103 在 V2 中表示可用存储空间不足 2 GB，而不是签名错误。

<!-- locator: A100V2-PRIVACY -->
## 6 隐私模式

长按遥控器静音键 2 秒可同时关闭麦克风与摄像头，屏幕显示橙色隐私图标。普通静音只关闭麦克风，不会关闭摄像头。
"""),

"EVAL-A200": ("智能会议终端 A200 用户手册", "1.3", "user_manual", r"""
# 智能会议终端 A200 用户手册

A200 面向大型会议室，系统版本为 3.1.x，不与 A100 共用升级包。

<!-- locator: A200-POWER -->
## 1 硬件安装

A200 主机使用 24 V/5 A 适配器，摄像机通过 PoE+ 交换机供电。机柜前后至少各留 15 cm，并保持进风温度低于 35℃。

<!-- locator: A200-CAPACITY -->
## 2 会议容量

A200 最多同时显示 25 路视频，可登记 200 个会议室模板，并支持双屏异显。双屏模式下第二块显示器必须支持 HDCP 2.2。

<!-- locator: A200-AUDIO -->
### 2.1 音频扩展

主机最多级联 4 个 M20 麦克风阵列。链路超过 30 米时必须使用光电转换模块；普通网线延长器不在支持范围内。

<!-- locator: A200-RECORD -->
## 3 录制

本地录制上限为 1080p，不支持本地 4K；如需 4K 录制必须启用云端高级录制服务。每小时 1080p 录制约占 2.5 GB。

<!-- locator: A200-HA -->
## 4 双机热备

两台 A200 可组成主备组。心跳连续丢失 6 次且累计超过 30 秒时触发切换；切换不会自动迁移正在写入的本地录制文件。

<!-- locator: A200-UPDATE -->
## 5 更新

A200 离线包扩展名为 `.a2k`。错误 U103 表示主备节点版本不一致，应先升级备用节点，再升级主节点。
"""),

"EVAL-DEPLOY": ("视频会议系统部署指南", "3.0", "deployment_guide", r"""
# 视频会议系统部署指南

本指南说明 A100 与 A200 在企业网络中的通用部署，不替代具体型号手册。

<!-- locator: DEPLOY-VLAN -->
## 1 网络分区

会议终端应放入独立的会议设备 VLAN。管理流量和媒体流量可以共享物理链路，但不得与访客 Wi-Fi 使用同一二层广播域。DHCP 租约建议不少于 24 小时。

<!-- locator: DEPLOY-PORTS -->
## 2 防火墙端口

| 用途 | 协议 | 端口 | 方向 |
|---|---|---:|---|
| 设备注册 | TCP | 443 | 出站 |
| 会议信令 | TCP | 8443 | 出站 |
| 实时媒体 | UDP | 30000-31999 | 双向 |
| 时间同步 | UDP | 123 | 出站 |

<!-- locator: DEPLOY-BANDWIDTH -->
## 3 带宽规划

单台终端的推荐预留带宽如下。数字是双向可用带宽，不是月度流量。

| 模式 | A100 V1 | A100 V2 | A200 |
|---|---:|---:|---:|
| 720p | 2 Mbps | 2 Mbps | 3 Mbps |
| 1080p | 4 Mbps | 4 Mbps | 6 Mbps |
| 双屏/4K | 不支持 | 12 Mbps | 16 Mbps |

<!-- locator: DEPLOY-QOS -->
## 4 QoS

音频媒体标记为 DSCP 46，视频媒体标记为 DSCP 34，信令标记为 DSCP 24。若网络设备会重写 DSCP，应在出口策略中重新标记，而不是在终端上反复保存配置。

<!-- locator: DEPLOY-DNS -->
## 5 DNS 与时间

终端必须解析 `meet.synthetic.example` 与 `update.synthetic.example`。NTP 偏差超过 90 秒会导致证书认证失败；推荐配置两个独立时间源。

<!-- locator: DEPLOY-ACCEPTANCE -->
## 6 上线验收

验收至少包括注册、呼入呼出、共享屏幕、20 分钟压力会议、断网重连和日志上传。只看到设备在线不能视为完成验收。
"""),

"EVAL-NETWORK": ("网络与连接故障排查手册", "2.2", "troubleshooting", r"""
# 网络与连接故障排查手册

<!-- locator: NET-NO-REGISTER -->
## 1 无法注册

先确认 DNS 能解析注册域名，再检查 TCP 443。若浏览器能访问门户但终端仍失败，应核对终端时间；偏差超过 90 秒会使 TLS 证书校验失败。不要首先恢复出厂设置。

<!-- locator: NET-NO-MEDIA -->
## 2 能入会但无音视频

信令成功但双向无媒体时，检查 UDP 30000-31999 是否放通以及 NAT 会话是否过早回收。单向无声还应交换测试麦克风和扬声器，区分网络与外设问题。

<!-- locator: NET-WIFI -->
## 3 无线频繁断开

RSSI 低于 -70 dBm 或同信道利用率超过 70% 时容易断开。优先调整 AP 位置和信道；不要通过提高所有 AP 发射功率掩盖漫游设计问题。

<!-- locator: NET-CODE-N201 -->
### 3.1 错误码 N201

N201 表示 DHCP 在 60 秒内未分配地址。检查 VLAN、地址池余量和 DHCP Relay。它不表示 DNS 故障。

<!-- locator: NET-CODE-N305 -->
### 3.2 错误码 N305

N305 表示媒体 UDP 建链超时。若只开放 TCP 8443，设备可以入会但不会获得实时媒体。

<!-- locator: NET-PROXY -->
## 4 代理限制

HTTP 代理仅承载注册、配置和升级流量，不转发 UDP 媒体。代理白名单不能替代防火墙的媒体端口策略。
"""),

"EVAL-WARRANTY": ("售后服务与保修政策", "2026.1", "policy", r"""
# 售后服务与保修政策

<!-- locator: WAR-TERM -->
## 1 保修期限

主机标准保修期为自签收日起 24 个月；原装适配器、遥控器和麦克风阵列为 12 个月。单独购买的延保必须在主机签收后 90 天内激活。

<!-- locator: WAR-EXCLUDE -->
## 2 不保修情形

进液、非授权拆机、使用错误电压适配器、雷击和超过工作温度造成的损坏不属于免费保修。正常外观磨损不影响功能时也不提供免费换新。

<!-- locator: WAR-RMA -->
## 3 返修流程

提交返修需提供序列号、购买凭证、故障时间、复现步骤和诊断包编号。服务台发出 RMA 编号后方可寄送；未经授权到付件会被拒收。

<!-- locator: WAR-SLA -->
## 4 服务响应

| 级别 | 示例 | 首次响应目标 | 更新频率 |
|---|---|---:|---:|
| S1 | 大面积会议中断 | 30 分钟 | 每 2 小时 |
| S2 | 单会议室核心功能不可用 | 4 小时 | 每工作日 |
| S3 | 咨询或非阻断缺陷 | 1 工作日 | 每 3 工作日 |

<!-- locator: WAR-DATA -->
## 5 数据处理

返修前客户应自行备份并删除本地录制。维修中心可能执行恢复出厂设置，且不承诺恢复设备中的会议记录。
"""),

"EVAL-ACCOUNT": ("企业账号与权限管理规范", "4.1", "governance", r"""
# 企业账号与权限管理规范

<!-- locator: ACC-ROLES -->
## 1 角色边界

组织管理员可管理租户、站点和审计策略；站点管理员只能管理被授权站点；会议运营员可创建会议和查看会议质量，但不能修改网络或导出全量审计日志。

<!-- locator: ACC-MFA -->
## 2 多因素认证

组织管理员和审计员必须启用 MFA。新账号首次登录后有 24 小时宽限期；宽限期结束仍未绑定验证器的账号会被暂停登录。

<!-- locator: ACC-LOCK -->
### 2.1 登录锁定

管理门户在连续 6 次密码失败后锁定账号 30 分钟。此规则与 A100 V2 设备端三次配对失败后的 20 分钟锁定无关。

<!-- locator: ACC-SERVICE -->
## 3 服务账号

服务账号不得用于交互登录，密钥最长有效期 90 天。每个服务账号必须登记负责人和用途；负责人离职时应在 24 小时内轮换密钥。

<!-- locator: ACC-OFFBOARD -->
## 4 离职与权限回收

人员离职后 4 小时内禁用账号，24 小时内移交其自动化任务。审计日志中应保留原账号标识，不得用删除账号的方式清除历史责任链。

<!-- locator: ACC-EXPORT -->
## 5 导出审批

导出全量成员列表需要组织管理员发起并由审计员批准。站点管理员只能导出本授权站点的成员摘要。
"""),

"EVAL-SECURITY": ("数据安全与日志管理规范", "5.0", "security_policy", r"""
# 数据安全与日志管理规范

<!-- locator: SEC-CLASS -->
## 1 数据分类

会议标题和参会人属于内部数据；会议录制、转写文本和屏幕共享截图属于敏感数据；公开发布的产品手册属于公开数据。分类取决于内容，不取决于文件扩展名。

<!-- locator: SEC-RETENTION -->
## 2 保留期限

管理操作审计日志保留 365 天，会议质量指标保留 180 天，普通设备运行日志保留 30 天。安全事件相关日志进入调查后可依法延长，但必须记录批准人和原因。

<!-- locator: SEC-RECORDING -->
### 2.1 会议录制

云端录制默认保留 90 天。会议所有者可缩短期限，但不能超过组织设置的上限。删除后进入 7 天恢复区，恢复区到期后不可由用户恢复。

<!-- locator: SEC-ENCRYPT -->
## 3 加密

传输使用 TLS 1.2 或更高版本；云端录制静态存储使用 AES-256。客户自备 USB 设备上的本地录制是否加密取决于 USB 自身能力，系统不会自动加密普通 U 盘。

<!-- locator: SEC-EXPORT -->
## 4 日志导出

全量审计日志导出需要组织管理员发起、审计员批准。导出包有效期 24 小时，下载链接最多使用 3 次。

<!-- locator: SEC-REDACT -->
## 5 日志脱敏

用于一般故障工单的日志必须掩码用户邮箱和公网 IP。涉及安全调查时可保留原值，但工单需标记“受限”并限定安全响应人员访问。
"""),

"EVAL-FAQ": ("企业会议设备常见问题 FAQ", "2026.08", "faq", r"""
# 企业会议设备常见问题 FAQ

<!-- locator: FAQ-MUTE -->
## 声音：为什么静音后摄像头还开着？

普通静音只关闭麦克风。A100 V2 可长按静音键 2 秒进入隐私模式，同时关闭麦克风和摄像头；A100 V1 与 A200 没有相同的遥控器快捷操作。

<!-- locator: FAQ-RECORD -->
## 录制：所有型号都能本地录 4K 吗？

不能。A100 V1 不支持本地 4K；A100 V2 在兼容 USB 3.0 存储设备上支持；A200 本地上限为 1080p，4K 需云端高级录制。

<!-- locator: FAQ-ONLINE -->
## 网络：显示在线是否代表部署完成？

不代表。在线只说明注册链路可用，还需要完成呼叫、共享、压力会议、断网重连和日志上传等验收项目。

<!-- locator: FAQ-U103 -->
## 更新：为什么不同设备都出现 U103？

错误码含义依型号和版本而变：A100 V1 是升级包签名不匹配，A100 V2 是可用空间不足 2 GB，A200 是主备版本不一致。排障前必须先确认型号和手册版本。

<!-- locator: FAQ-FACTORY -->
## 恢复：按复位键会不会马上清空？

A100 V1 需要持续按 12 秒才会恢复出厂；A100 V2 按 8 秒只进入恢复菜单，还需二次确认。短按通常只是重启，操作前仍应备份。

<!-- locator: FAQ-PROXY -->
## 网络：配置代理后还要开放 UDP 吗？

需要。代理只处理注册、配置和升级流量，不承载实时 UDP 媒体。
"""),

"EVAL-OPS": ("运维故障处理手册", "3.4", "operations_runbook", r"""
# 运维故障处理手册

<!-- locator: OPS-SEVERITY -->
## 1 事件分级

影响三个及以上会议室且无法绕过的故障定为 P1；单会议室核心功能中断为 P2；有替代方案的性能下降为 P3。P1/P2/P3 是内部事件优先级，不等同于售后 S1/S2/S3 服务等级。

<!-- locator: OPS-P1 -->
## 2 P1 处理

值班人员应在 10 分钟内确认事件，15 分钟内建立协同频道，并每 30 分钟更新一次状态。未经事件指挥批准不得批量恢复出厂。

<!-- locator: OPS-LOGS -->
## 3 证据采集

采集时间范围应覆盖故障前后各 15 分钟，记录终端序列号、站点、会议 ID、网络路径和时钟偏差。普通工单上传前必须按安全规范脱敏。

<!-- locator: OPS-ROLLBACK -->
## 4 变更回退

升级后 30 分钟内出现批量注册失败，应暂停后续批次、保留一台故障样机，并按对应型号手册执行版本回退。不得拿 A100 V2 的 `.a2u` 包回退 A200。

<!-- locator: OPS-CLOSE -->
## 5 关闭事件

恢复服务后至少观察 60 分钟。关闭记录必须包含影响范围、根因状态、临时措施、长期行动项和负责人；根因未知时应明确写“待分析”，不能推测填充。

<!-- locator: OPS-CHECKLIST -->
## 6 快速检查表

| 现象 | 首查项 | 禁止的第一动作 |
|---|---|---|
| 无法注册 | DNS、TCP 443、时间 | 恢复出厂 |
| 能入会无媒体 | UDP 30000-31999、NAT | 更换账号 |
| 无线掉线 | RSSI、信道利用率 | 提高全部 AP 功率 |
| 升级失败 | 型号、包格式、空间 | 反复强制断电 |
"""),
}

LOCATOR_RE = re.compile(r"<!-- locator: ([A-Z0-9-]+) -->\n(.*?)(?=\n#{1,6} |\Z)", re.S)


def doc_text(document_id: str, title: str, version: str, document_type: str, body: str) -> str:
    front = (
        "---\n"
        f"document_id: {document_id}\n"
        f"title: {title}\n"
        f"version: \"{version}\"\n"
        f"document_type: {document_type}\n"
        "synthetic: true\n"
        "evaluation_only: true\n"
        "---\n\n"
    )
    # Put locators inside their heading chunk. The source authoring form keeps
    # markers before headings for readability; rendered Markdown moves each
    # marker immediately below that heading so the production chunker retains it.
    rendered_body = re.sub(
        r"<!-- locator: ([A-Z0-9-]+) -->\n(#{1,6} [^\n]+)",
        r"\2\n\n<!-- locator: \1 -->",
        body.strip(),
    )
    context = SECTION_CONTEXT[document_type]
    rendered_body = re.sub(
        r"(<!-- locator: [A-Z0-9-]+ -->\n.*?)(?=\n#{1,6} |\Z)",
        lambda match: match.group(1).rstrip() + "\n\n" + CONTEXT_MARKER + "\n\n" + context + "\n",
        rendered_body,
        flags=re.S,
    )
    return NOTICE + "\n" + front + rendered_body + "\n"


def locator_index(rendered: dict[str, str]) -> dict[str, dict[str, str]]:
    index = {}
    for document_id, text in rendered.items():
        for locator, block in LOCATOR_RE.findall(text):
            evidence_block = block.split(CONTEXT_MARKER, 1)[0]
            evidence = " ".join(line.strip() for line in evidence_block.splitlines() if line.strip())
            if locator in index:
                raise ValueError(f"duplicate locator: {locator}")
            index[locator] = {"document_id": document_id, "evidence": evidence}
    return index


# category, query, locators, reference answer, difficulty, parent?, multi?, expected version, notes
CASE_SPECS = [
    # Exact facts (28)
    ("exact_fact","A100 V1 使用什么规格的电源适配器？",["A100V1-POWER"],"12 V/3 A 圆口适配器。","easy",False,False,"1.0","明确硬件事实。"),
    ("exact_fact","A100 V2 正常启动大约需要多久？",["A100V2-POWER"],"约 25 秒。","easy",False,False,"2.0","版本明确的启动参数。"),
    ("exact_fact","A200 机柜进风温度上限是多少？",["A200-POWER"],"应低于 35℃。","easy",False,False,"1.3","环境约束。"),
    ("exact_fact","A100 V1 的配对码有效几分钟？",["A100V1-PAIR"],"10 分钟。","easy",False,False,"1.0","短事实。"),
    ("exact_fact","A100 V2 配对连续错误几次会锁定？",["A100V2-PAIR"],"连续 3 次。","easy",False,False,"2.0","版本特定阈值。"),
    ("exact_fact","A200 最多能级联多少个 M20 麦克风阵列？",["A200-AUDIO"],"4 个。","easy",False,False,"1.3","容量事实。"),
    ("exact_fact","终端注册需要放通哪个 TCP 端口？",["DEPLOY-PORTS"],"TCP 443 出站。","easy",False,False,None,"端口表事实。"),
    ("exact_fact","视频媒体应该使用哪个 DSCP 值？",["DEPLOY-QOS"],"DSCP 34。","easy",False,False,None,"网络配置事实。"),
    ("exact_fact","NTP 偏差超过多少会导致证书认证失败？",["DEPLOY-DNS"],"90 秒。","easy",False,False,None,"通用部署事实。"),
    ("exact_fact","N201 错误码是什么意思？",["NET-CODE-N201"],"DHCP 在 60 秒内未分配地址。","easy",False,False,None,"错误码事实。"),
    ("exact_fact","N305 应重点检查哪段端口？",["NET-CODE-N305"],"UDP 30000-31999。","easy",False,False,None,"错误码与端口。"),
    ("exact_fact","主机标准保修期是多久？",["WAR-TERM"],"自签收日起 24 个月。","easy",False,False,None,"政策事实。"),
    ("exact_fact","延保最晚应在签收后多久激活？",["WAR-TERM"],"90 天内。","easy",False,False,None,"政策期限。"),
    ("exact_fact","S1 售后事件首次响应目标是多少？",["WAR-SLA"],"30 分钟。","easy",False,False,None,"服务表事实。"),
    ("exact_fact","组织管理员首次登录后有多久绑定 MFA？",["ACC-MFA"],"24 小时宽限期。","easy",False,False,None,"账号安全事实。"),
    ("exact_fact","服务账号密钥最长有效期是多少？",["ACC-SERVICE"],"90 天。","easy",False,False,None,"密钥规则。"),
    ("exact_fact","人员离职后多久内应禁用账号？",["ACC-OFFBOARD"],"4 小时内。","easy",False,False,None,"权限回收。"),
    ("exact_fact","管理操作审计日志保留多久？",["SEC-RETENTION"],"365 天。","easy",False,False,None,"保留期。"),
    ("exact_fact","普通设备运行日志保留多久？",["SEC-RETENTION"],"30 天。","easy",False,False,None,"同段不同数据。"),
    ("exact_fact","云端录制删除后恢复区保留多久？",["SEC-RECORDING"],"7 天。","easy",False,False,None,"恢复窗口。"),
    ("exact_fact","审计日志导出链接最多可下载几次？",["SEC-EXPORT"],"3 次。","easy",False,False,None,"导出限制。"),
    ("exact_fact","A100 V2 怎样同时关闭摄像头和麦克风？",["A100V2-PRIVACY"],"长按遥控器静音键 2 秒进入隐私模式。","easy",False,False,"2.0","设备操作。"),
    ("exact_fact","P1 事件多久更新一次状态？",["OPS-P1"],"每 30 分钟。","easy",False,False,None,"运维时限。"),
    ("exact_fact","事件恢复后至少观察多久才能关闭？",["OPS-CLOSE"],"至少 60 分钟。","easy",False,False,None,"关闭条件。"),
    ("exact_fact","A100 V1 离线升级包是什么扩展名？",["A100V1-UPDATE"],".a1u。","easy",False,False,"1.0","包格式。"),
    ("exact_fact","A200 离线升级包扩展名是什么？",["A200-UPDATE"],".a2k。","easy",False,False,"1.3","包格式干扰。"),
    ("exact_fact","A200 主备切换的心跳条件是什么？",["A200-HA"],"连续丢失 6 次且累计超过 30 秒。","medium",False,False,"1.3","复合阈值。"),
    ("exact_fact","返修寄送前必须先获得什么编号？",["WAR-RMA"],"服务台发出的 RMA 编号。","easy",False,False,None,"流程事实。"),
    # Paraphrase/colloquial (18)
    ("paraphrase_colloquial","一代 A100 老是输错那个六位数，会被晾多久？",["A100V1-PAIR"],"输错 5 次后暂停配对入口 15 分钟。","medium",False,False,"1.0","口语化且避免原句。"),
    ("paraphrase_colloquial","二代小终端密码试三回都不对，是整台机器都不能用了吗？",["A100V2-PAIR"],"不是；锁定的是当前管理员账号 20 分钟，其他授权管理员仍可登录。","medium",False,False,"2.0","区分账号与设备。"),
    ("paraphrase_colloquial","会议能进去，可大家互相都听不见也看不到，网络先查哪儿？",["NET-NO-MEDIA"],"先查 UDP 30000-31999 和 NAT 会话回收。","medium",False,False,None,"症状表达替代术语。"),
    ("paraphrase_colloquial","网页门户没问题，盒子死活认证不上，别急着重置的话先看什么？",["NET-NO-REGISTER"],"先查 DNS、TCP 443 和终端时间偏差。","medium",False,False,None,"多步排障。"),
    ("paraphrase_colloquial","Wi-Fi 信号已经很差了，把每个 AP 功率都拉满是不是最快？",["NET-WIFI"],"不是；优先调整 AP 位置和信道，不应把所有 AP 功率都提高。","medium",False,False,None,"反事实问法。"),
    ("paraphrase_colloquial","给盒子配了网页代理，是不是媒体端口就不用开了？",["NET-PROXY"],"不是；代理不转发 UDP 媒体，媒体端口仍需放通。","medium",False,False,None,"常见误解。"),
    ("paraphrase_colloquial","机器进水了还在两年内，能不能免费修？",["WAR-EXCLUDE"],"不能；进液属于免费保修排除情形。","easy",False,False,None,"自然政策提问。"),
    ("paraphrase_colloquial","管理员一直没绑验证器，过了一天账号会怎样？",["ACC-MFA"],"宽限期结束后暂停登录。","medium",False,False,None,"结果型提问。"),
    ("paraphrase_colloquial","员工走人以后，能不能直接把账号删了省事？",["ACC-OFFBOARD"],"不能；应禁用并保留原账号标识以维持审计责任链。","medium",False,False,None,"反向规则。"),
    ("paraphrase_colloquial","普通 U 盘插终端录会，系统会顺手把文件加密吗？",["SEC-ENCRYPT"],"不会；本地录制加密取决于 USB 自身能力。","medium",False,False,None,"口语化安全问题。"),
    ("paraphrase_colloquial","工单日志里带着同事邮箱和公网地址，可以原样上传吗？",["SEC-REDACT"],"一般故障工单不可以，必须掩码；安全调查需受限标记。","medium",False,False,None,"场景化规则。"),
    ("paraphrase_colloquial","终端亮着在线绿点，就算会议室交付完了吗？",["FAQ-ONLINE"],"不算，还需完成呼叫、共享、压力会议、断网重连和日志上传验收。","medium",False,False,None,"避免复述标题。"),
    ("paraphrase_colloquial","A100 二代按住复位八秒会不会直接全清？",["A100V2-RESET"],"不会，只进入恢复菜单，还需二次确认。","medium",False,False,"2.0","版本恢复差异。"),
    ("paraphrase_colloquial","大会议室主机录一小时 1080p，大概得留多少盘？",["A200-RECORD"],"约 2.5 GB。","medium",False,False,"1.3","单位与口语。"),
    ("paraphrase_colloquial","线上升级后好多房间突然注册不了，运维第一步该怎么收手？",["OPS-ROLLBACK"],"暂停后续批次、保留故障样机，并按对应型号手册回退。","hard",False,False,None,"复合操作。"),
    ("paraphrase_colloquial","故障原因还没查明，关单时能先猜一个填上吗？",["OPS-CLOSE"],"不能，应明确写“待分析”。","medium",False,False,None,"流程约束。"),
    ("paraphrase_colloquial","公网出口把语音优先级标签洗掉了，终端反复保存有用吗？",["DEPLOY-QOS"],"不应反复保存终端配置，应在出口策略重新标记 DSCP。","hard",False,False,None,"网络术语改写。"),
    ("paraphrase_colloquial","想把会议盒子塞在访客无线同一个二层网里，规范允许吗？",["DEPLOY-VLAN"],"不允许，会议设备不得与访客 Wi-Fi 共用二层广播域。","medium",False,False,None,"架构规则。"),
    # Parent context (12)
    ("parent_context","A100 V1 的“配对”小节中，输错后暂停的是哪项入口？",["A100V1-PAIR"],"配对入口。","medium",True,False,"1.0","子标题需结合产品版本。"),
    ("parent_context","A100 V2 网络接入里的证书必须带什么标识？",["A100V2-NET"],"设备序列号。","medium",True,False,"2.0","父级产品与网络主题共同限定。"),
    ("parent_context","A200 音频扩展链路超过 30 米时要加什么？",["A200-AUDIO"],"光电转换模块。","medium",True,False,"1.3","依赖上级音频语境。"),
    ("parent_context","部署指南的 DNS 与时间章节建议配置几个时间源？",["DEPLOY-DNS"],"两个独立时间源。","medium",True,False,None,"章节路径限定。"),
    ("parent_context","无线故障章节中的 N201 不是哪类故障？",["NET-CODE-N201"],"不是 DNS 故障。","hard",True,False,None,"相似错误码干扰。"),
    ("parent_context","保修政策的数据处理章节提醒返修前删除什么？",["WAR-DATA"],"本地录制。","medium",True,False,None,"通用标题依赖父文档。"),
    ("parent_context","账号规范的登录锁定小节规定门户锁多久？",["ACC-LOCK"],"30 分钟。","medium",True,False,None,"与设备端锁定相似。"),
    ("parent_context","安全规范的会议录制小节中，默认云端保留期是多少？",["SEC-RECORDING"],"90 天。","medium",True,False,None,"父级主题避免日志保留混淆。"),
    ("parent_context","FAQ 的声音条目说明普通静音不会关掉什么？",["FAQ-MUTE"],"摄像头。","medium",True,False,None,"标题提供问题主题。"),
    ("parent_context","运维手册的证据采集章节要求故障前后各覆盖多久？",["OPS-LOGS"],"各 15 分钟。","medium",True,False,None,"通用数值需父语境。"),
    ("parent_context","部署验收章节说哪一种状态本身不能算交付完成？",["DEPLOY-ACCEPTANCE"],"仅看到设备在线。","medium",True,False,None,"父标题补充验收语境。"),
    ("parent_context","A200 更新章节里的 U103 要先升级哪个节点？",["A200-UPDATE"],"备用节点。","hard",True,False,"1.3","同码异义且需父产品。"),
    # Version / similar document confusion (12)
    ("version_confusion","A100 V1 和 V2 的供电方式分别是什么？",["A100V1-POWER","A100V2-POWER"],"V1 为 12 V/3 A 圆口；V2 为 USB-C PD 45 W。","hard",False,True,"1.0|2.0","同型号跨版本。"),
    ("version_confusion","A100 两代配对失败的次数和锁定时间有什么变化？",["A100V1-PAIR","A100V2-PAIR"],"V1 错 5 次暂停入口 15 分钟；V2 错 3 次锁当前管理员 20 分钟。","hard",False,True,"1.0|2.0","相似流程关键数字不同。"),
    ("version_confusion","A100 V1 与 V2 分别能保存多少常用会议室？",["A100V1-MEETING","A100V2-MEETING"],"V1 为 20 个，V2 为 50 个。","hard",False,True,"1.0|2.0","版本容量。"),
    ("version_confusion","A100 V2 的 U103 能按 V1 的签名错误处理吗？",["A100V1-UPDATE","A100V2-UPDATE"],"不能；V2 表示空间不足 2 GB，V1 才表示签名不匹配。","hard",False,True,"1.0|2.0","同错误码异义。"),
    ("version_confusion","A100 V1 与 V2 恢复出厂的按键流程相同吗？",["A100V1-RESET","A100V2-RESET"],"不同；V1 按 12 秒直接恢复，V2 按 8 秒进入菜单后还需确认。","hard",False,True,"1.0|2.0","恢复流程混淆。"),
    ("version_confusion","A100 V2 与 A200 哪个支持本地 4K 录制？",["A100V2-MEETING","A200-RECORD"],"A100 V2 在兼容 USB 3.0 设备上支持；A200 本地仅 1080p。","hard",False,True,"2.0|1.3","相似产品能力。"),
    ("version_confusion","A100 V1、V2、A200 的离线升级包分别是什么？",["A100V1-UPDATE","A100V2-UPDATE","A200-UPDATE"],"依次为 .a1u、.a2u、.a2k。","hard",False,True,"1.0|2.0|1.3","三文档包格式。"),
    ("version_confusion","A100 V1 和 V2 的有线网络速率差多少？",["A100V1-NET","A100V2-NET"],"V1 为 100 Mbps，V2 为 1 Gbps。","hard",False,True,"1.0|2.0","同章节版本差异。"),
    ("version_confusion","A100 V2 的账号锁定与管理门户账号锁定是否同一规则？",["A100V2-PAIR","ACC-LOCK"],"不是；设备端为配对错 3 次锁 20 分钟，门户为密码错 6 次锁 30 分钟。","hard",False,True,"2.0","相同关键词不同业务。"),
    ("version_confusion","售后 S1 与运维 P1 是同一个分级吗？",["WAR-SLA","OPS-SEVERITY"],"不是；S 级是售后服务等级，P 级是内部事件优先级。","hard",False,True,None,"相似分级体系。"),
    ("version_confusion","A100 V1 和 A200 都不能本地录 4K，但替代方案一样吗？",["A100V1-MEETING","A200-RECORD"],"都可依赖云端能力，但 A200 明确需要云端高级录制；V1 取决于企业订阅。","hard",False,True,"1.0|1.3","相似结论细节不同。"),
    ("version_confusion","U103 出现在 A200 上时，清理 2 GB 空间是否正确？",["A100V2-UPDATE","A200-UPDATE"],"不正确；A200 的 U103 是主备版本不一致，空间不足 2 GB 是 A100 V2 的含义。","hard",False,True,"1.3|2.0","错误码干扰。"),
    # Multi-document (10)
    ("multi_document","部署一台 A100 V2 做 4K 会议，需要预留多少带宽且设备侧还需满足什么录制条件？",["DEPLOY-BANDWIDTH","A100V2-MEETING"],"预留双向 12 Mbps；本地录制还需兼容的 USB 3.0 存储设备。","hard",False,True,"2.0","部署表与产品手册组合。"),
    ("multi_document","A200 无媒体时应查哪些端口，同时它的双屏显示器有什么要求？",["NET-NO-MEDIA","A200-CAPACITY"],"查 UDP 30000-31999 和 NAT；第二屏需支持 HDCP 2.2。","hard",False,True,"1.3","跨网络与设备。"),
    ("multi_document","返修 A100 前，返修申请要准备什么，随工单提交的日志又应怎样保护隐私？",["WAR-RMA","SEC-REDACT"],"返修申请准备序列号、购买凭证、故障时间、复现步骤和诊断包编号；普通工单日志需掩码邮箱和公网 IP。","hard",False,True,None,"跨售后与安全规范。"),
    ("multi_document","普通故障工单采集日志时，时间范围和隐私处理分别怎么做？",["OPS-LOGS","SEC-REDACT"],"覆盖故障前后各 15 分钟，并掩码邮箱和公网 IP。","hard",False,True,None,"跨运维与安全规范。"),
    ("multi_document","会议终端部署到访客网是否可行，为什么仅显示在线还不能交付？",["DEPLOY-VLAN","FAQ-ONLINE"],"不可与访客 Wi-Fi 共二层广播域；在线只代表注册可用，还需呼叫、共享、压力会议、重连和日志上传。","hard",False,True,None,"跨部署指南与 FAQ。"),
    ("multi_document","A100 V2 启用 EAP-TLS 后仍认证失败，除了证书内容还应检查什么时间条件？",["A100V2-NET","DEPLOY-DNS"],"证书需含设备序列号，并检查 NTP 偏差不得超过 90 秒。","hard",False,True,"2.0","产品与通用部署。"),
    ("multi_document","升级后批量注册失败时，回退动作和网络首查项是什么？",["OPS-ROLLBACK","NET-NO-REGISTER"],"暂停批次并按型号回退；网络侧先查 DNS、TCP 443 和终端时间。","hard",False,True,None,"变更与网络排障。"),
    ("multi_document","组织管理员导出全量审计日志需要什么审批，下载包又有什么限制？",["ACC-EXPORT","SEC-EXPORT"],"组织管理员发起、审计员批准；导出包 24 小时有效且最多下载 3 次。","hard",False,True,None,"权限和数据规则。"),
    ("multi_document","A200 建主备后升级 U103，应该按什么顺序处理，事件关闭还需观察多久？",["A200-UPDATE","OPS-CLOSE"],"先升级备用节点再升级主节点；恢复后至少观察 60 分钟。","hard",False,True,"1.3","设备与运维闭环。"),
    ("multi_document","A100 V2 进入隐私模式的操作是什么，FAQ 对普通静音又如何说明？",["A100V2-PRIVACY","FAQ-MUTE"],"长按静音键 2 秒；普通静音只关麦克风，不关摄像头。","medium",False,True,"2.0","手册与 FAQ 一致性。"),
    # Table (8)
    ("table","A100 V2 跑双屏或 4K 时建议预留多少双向带宽？",["DEPLOY-BANDWIDTH"],"12 Mbps。","medium",False,False,"2.0","表格单元格。"),
    ("table","A200 的 1080p 推荐带宽是多少？",["DEPLOY-BANDWIDTH"],"6 Mbps。","medium",False,False,"1.3","相邻型号干扰。"),
    ("table","实时媒体的协议、端口范围和方向分别是什么？",["DEPLOY-PORTS"],"UDP、30000-31999、双向。","medium",False,False,None,"多列表格。"),
    ("table","S2 服务事件多久首次响应，后续多久更新一次？",["WAR-SLA"],"4 小时首次响应，每工作日更新。","medium",False,False,None,"服务表。"),
    ("table","有替代方案的性能下降属于哪个内部事件级别？",["OPS-SEVERITY"],"P3。","medium",False,False,None,"正文分级，与 S3 干扰。"),
    ("table","无线掉线时快速检查表禁止先做什么？",["OPS-CHECKLIST"],"禁止先提高全部 AP 功率。","medium",False,False,None,"运维表。"),
    ("table","升级失败在快速检查表里首查哪三项？",["OPS-CHECKLIST"],"型号、包格式、空间。","medium",False,False,None,"表格枚举。"),
    ("table","A100 V1 在 1080p 模式的推荐双向带宽是多少？",["DEPLOY-BANDWIDTH"],"4 Mbps。","medium",False,False,"1.0","版本与表格。"),
    # No-answer / negatives (22)
    ("no_answer","A300 会议终端最多支持多少路视频？",[],"知识库没有 A300 型号信息，无法确定。","hard",False,False,None,"不存在的型号。"),
    ("no_answer","A100 V2 的摄像头传感器尺寸是多少？",[],"现有文档未提供传感器尺寸。","medium",False,False,"2.0","合理但缺失的规格。"),
    ("no_answer","A200 的整机重量是多少公斤？",[],"现有文档未提供重量。","medium",False,False,"1.3","缺失硬件参数。"),
    ("no_answer","公司是否报销家庭宽带用于远程会议？",[],"知识库没有费用报销政策。","easy",False,False,None,"域外政策。"),
    ("no_answer","主机保修期内是否承诺直接换新而不是维修？",[],"文档未承诺保修期内直接换新。","hard",False,False,None,"看似合理但无证据。"),
    ("no_answer","S1 故障一定会在两小时内彻底解决吗？",[],"文档只有首次响应和更新频率，没有解决时限。","hard",False,False,None,"不可从 SLA 推断。"),
    ("no_answer","A100 V2 为什么在某个房间每天早上九点断网？",[],"文档不足以确定该具体故障的根因。","hard",False,False,"2.0","未知原因类。"),
    ("no_answer","会议录制是否可以永久保留且永不删除？",[],"文档没有永久保留政策。","medium",False,False,None,"不存在的政策。"),
    ("no_answer","审计日志导出包的加密密码是什么？",[],"文档未提供导出包密码。","medium",False,False,None,"安全敏感且缺失。"),
    ("no_answer","A100 V1 支持蓝牙 5.3 吗？",[],"文档没有蓝牙版本信息。","medium",False,False,"1.0","缺失无线规格。"),
    ("exact_fact","A200 能否连接 8 个 M20 阵列？",["A200-AUDIO"],"不能；文档明确主机最多级联 4 个 M20 麦克风阵列。","medium",False,False,"1.3","Freeze 前审查确认该问题可由容量上限直接回答。"),
    ("no_answer","网络团队应该购买哪个品牌的交换机？",[],"知识库没有品牌采购建议。","easy",False,False,None,"采购域外。"),
    ("no_answer","EAP-TLS 证书应由哪一家 CA 签发？",[],"文档未指定 CA。","hard",False,False,None,"细节缺失。"),
    ("no_answer","云端高级录制服务每月多少钱？",[],"知识库没有价格信息。","easy",False,False,None,"价格缺失。"),
    ("no_answer","P1 事件的根因分析必须在几天内完成？",[],"文档没有规定根因分析完成期限。","hard",False,False,None,"运维期限缺失。"),
    ("no_answer","离职员工的个人网盘文件由谁继承？",[],"知识库只规定自动化任务移交，没有个人网盘规则。","hard",False,False,None,"相邻政策干扰。"),
    ("exact_fact","本地 USB 录制一定符合 AES-256 吗？",["SEC-ENCRYPT"],"不一定；文档明确本地录制是否加密取决于 USB 自身能力，系统不会自动加密普通 U 盘。","hard",False,False,None,"Freeze 前审查确认源文档可直接支持否定答案。"),
    ("no_answer","设备发生雷击后维修中心收费多少？",[],"文档说明雷击不免费保修，但未给收费金额。","medium",False,False,None,"部分相关但答案缺失。"),
    ("no_answer","会议室模板能否自动同步到个人日历？",[],"文档没有日历同步信息。","medium",False,False,None,"功能缺失。"),
    ("no_answer","A100 V2 在线升级平均需要几分钟？",[],"文档支持在线升级，但没有平均耗时。","hard",False,False,"2.0","性能数字不可推断。"),
    ("no_answer","N305 是否由某个特定运营商网络导致？",[],"N305 说明媒体 UDP 超时，无法据此确定运营商原因。","hard",False,False,None,"原因归因不足。"),
    ("no_answer","公司允许员工用私人手机录制会议吗？",[],"现有知识库没有私人手机录制政策。","medium",False,False,None,"合理企业问题但无证据。"),
]


def build() -> None:
    for path in (DOC_DIR, DATASET_PATH.parent, MANIFEST_PATH.parent):
        path.mkdir(parents=True, exist_ok=True)

    rendered = {}
    document_manifest = []
    for document_id, (title, version, document_type, body) in DOCUMENTS.items():
        text = doc_text(document_id, title, version, document_type, body)
        rendered[document_id] = text
        file_name = document_id.lower() + ".md"
        path = DOC_DIR / file_name
        path.write_text(text, encoding="utf-8")
        document_manifest.append({
            "document_id": document_id,
            "title": title,
            "version": version,
            "document_type": document_type,
            "synthetic": True,
            "path": f"documents/{file_name}",
            "sha256": hashlib.sha256(text.encode()).hexdigest(),
        })

    locators = locator_index(rendered)
    cases = []
    for number, spec in enumerate(CASE_SPECS, start=1):
        category, query, locator_ids, answer, difficulty, parent, multi, expected_version, notes = spec
        relevant_documents = sorted({locators[x]["document_id"] for x in locator_ids})
        evidence = [locators[x]["evidence"] for x in locator_ids]
        tags = []
        primary_tag = {
            "paraphrase_colloquial": "paraphrase",
            "parent_context": "parent_context",
            "version_confusion": "version_confusion",
            "multi_document": "multi_document",
            "table": "table",
            "no_answer": "no_answer",
        }.get(category)
        if primary_tag:
            tags.append(primary_tag)
        if parent and "parent_context" not in tags:
            tags.append("parent_context")
        if multi and "multi_document" not in tags:
            tags.append("multi_document")
        if category == "version_confusion":
            tags.append("similar_document")
        if len(relevant_documents) > 1 and "multi_document" not in tags:
            tags.append("multi_document")
        if any(x in {"DEPLOY-BANDWIDTH", "DEPLOY-PORTS", "WAR-SLA", "OPS-CHECKLIST"} for x in locator_ids) and "table" not in tags:
            tags.append("table")
        cases.append({
            "query_id": f"v2q{number:03d}",
            "query": query,
            "category": category,
            "answerable": bool(locator_ids),
            "relevant_documents": relevant_documents,
            "relevant_locators": locator_ids,
            "reference_answer": answer,
            "evidence": evidence,
            "notes": notes,
            "tags": tags,
            "difficulty": difficulty,
            "requires_parent_context": parent,
            "requires_multi_document": multi,
            "expected_version": expected_version,
            "review_status": "self_reviewed",
        })

    dataset = {
        "schema_version": 2,
        "dataset_id": "rag-evaluation-v2-enterprise-smart-office-draft",
        "status": "READY_FOR_HUMAN_REVIEW",
        "synthetic": True,
        "created_at": CREATED_AT,
        "ground_truth_policy": "Labels are authored only from source Markdown locators; no retrieval or reranker output was consulted.",
        "cases": cases,
    }
    dataset_bytes = (json.dumps(dataset, ensure_ascii=False, indent=2) + "\n").encode()
    DATASET_PATH.write_bytes(dataset_bytes)

    corpus_hash_input = "".join(
        f"{item['document_id']}:{item['sha256']}\n" for item in sorted(document_manifest, key=lambda x: x["document_id"])
    ).encode()
    manifest = {
        "status": "DRAFT_MANIFEST_NOT_FROZEN",
        "created_at": CREATED_AT,
        "dataset_path": "dataset/dataset_v2_draft.json",
        "dataset_sha256": hashlib.sha256(dataset_bytes).hexdigest(),
        "document_manifest_sha256": hashlib.sha256(corpus_hash_input).hexdigest(),
        "query_count": len(cases),
        "category_distribution": dict(sorted(Counter(x["category"] for x in cases).items())),
        "tag_distribution": dict(sorted(Counter(tag for x in cases for tag in x["tags"]).items())),
        "answerable_count": sum(x["answerable"] for x in cases),
        "no_answer_count": sum(not x["answerable"] for x in cases),
        "documents": document_manifest,
        "freeze_warning": "This hash records the review draft only. It is not a FROZEN EVALUATION SET.",
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Built {len(rendered)} documents, {len(locators)} locators, {len(cases)} draft queries")


if __name__ == "__main__":
    build()
