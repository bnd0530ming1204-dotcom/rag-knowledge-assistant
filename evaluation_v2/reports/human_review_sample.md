# Evaluation V2 — Human Review Sample

> **SYNTHETIC / FOR EVALUATION ONLY**

> Status: `READY_FOR_HUMAN_REVIEW`. Reviewing this file does not freeze the dataset.

Check whether each question is natural, answerability is correct, every source supports the reference answer, and the test value is genuine rather than benchmark decoration.

## 1. v2q001

- **Query:** A100 V1 使用什么规格的电源适配器？
- **Category:** `exact_fact`
- **Answerable:** `true`
- **Ground Truth Document:** EVAL-A100-V1
- **Ground Truth Locator:** A100V1-POWER
- **Ground Truth Evidence:** A100 V1 使用 12 V/3 A 圆口适配器。通电后状态灯先呈白色约 40 秒，完成启动后转为绿色。安装时应在设备两侧各保留至少 8 cm 散热空间，不得放入封闭抽屉。
- **Reference Answer:** 12 V/3 A 圆口适配器。
- **Why valuable:** 明确硬件事实。
- **Special flag:** `LEXICAL_LEAKAGE_CANDIDATE`
- **Human decision:** [ ] accept  [ ] revise  [ ] reject
- **Reviewer note:**

## 2. v2q005

- **Query:** A100 V2 配对连续错误几次会锁定？
- **Category:** `exact_fact`
- **Answerable:** `true`
- **Ground Truth Document:** EVAL-A100-V2
- **Ground Truth Locator:** A100V2-PAIR
- **Ground Truth Evidence:** 六位配对码有效期缩短为 5 分钟。连续输入错误 3 次后，当前管理员账号锁定 20 分钟；其他已授权管理员仍可登录。
- **Reference Answer:** 连续 3 次。
- **Why valuable:** 版本特定阈值。
- **Special flag:** `LEXICAL_LEAKAGE_CANDIDATE`
- **Human decision:** [ ] accept  [ ] revise  [ ] reject
- **Reviewer note:**

## 3. v2q010

- **Query:** N201 错误码是什么意思？
- **Category:** `exact_fact`
- **Answerable:** `true`
- **Ground Truth Document:** EVAL-NETWORK
- **Ground Truth Locator:** NET-CODE-N201
- **Ground Truth Evidence:** N201 表示 DHCP 在 60 秒内未分配地址。检查 VLAN、地址池余量和 DHCP Relay。它不表示 DNS 故障。
- **Reference Answer:** DHCP 在 60 秒内未分配地址。
- **Why valuable:** 错误码事实。
- **Special flag:** `GENERAL_REPRESENTATIVE`
- **Human decision:** [ ] accept  [ ] revise  [ ] reject
- **Reviewer note:**

## 4. v2q018

- **Query:** 管理操作审计日志保留多久？
- **Category:** `exact_fact`
- **Answerable:** `true`
- **Ground Truth Document:** EVAL-SECURITY
- **Ground Truth Locator:** SEC-RETENTION
- **Ground Truth Evidence:** 管理操作审计日志保留 365 天，会议质量指标保留 180 天，普通设备运行日志保留 30 天。安全事件相关日志进入调查后可依法延长，但必须记录批准人和原因。
- **Reference Answer:** 365 天。
- **Why valuable:** 保留期。
- **Special flag:** `GENERAL_REPRESENTATIVE`
- **Human decision:** [ ] accept  [ ] revise  [ ] reject
- **Reviewer note:**

## 5. v2q029

- **Query:** 一代 A100 老是输错那个六位数，会被晾多久？
- **Category:** `paraphrase_colloquial`
- **Answerable:** `true`
- **Ground Truth Document:** EVAL-A100-V1
- **Ground Truth Locator:** A100V1-PAIR
- **Ground Truth Evidence:** 管理员在终端输入六位配对码，配对码有效期 10 分钟。连续输入错误 5 次后，配对入口暂停 15 分钟，但设备本身不会退出已加入的会议。
- **Reference Answer:** 输错 5 次后暂停配对入口 15 分钟。
- **Why valuable:** 口语化且避免原句。
- **Special flag:** `GENERAL_REPRESENTATIVE`
- **Human decision:** [ ] accept  [ ] revise  [ ] reject
- **Reviewer note:**

## 6. v2q030

- **Query:** 二代小终端密码试三回都不对，是整台机器都不能用了吗？
- **Category:** `paraphrase_colloquial`
- **Answerable:** `true`
- **Ground Truth Document:** EVAL-A100-V2
- **Ground Truth Locator:** A100V2-PAIR
- **Ground Truth Evidence:** 六位配对码有效期缩短为 5 分钟。连续输入错误 3 次后，当前管理员账号锁定 20 分钟；其他已授权管理员仍可登录。
- **Reference Answer:** 不是；锁定的是当前管理员账号 20 分钟，其他授权管理员仍可登录。
- **Why valuable:** 区分账号与设备。
- **Special flag:** `DIFFICULT / WRONG-SCOPE RISK`
- **Human decision:** [ ] accept  [ ] revise  [ ] reject
- **Reviewer note:**

## 7. v2q033

- **Query:** Wi-Fi 信号已经很差了，把每个 AP 功率都拉满是不是最快？
- **Category:** `paraphrase_colloquial`
- **Answerable:** `true`
- **Ground Truth Document:** EVAL-NETWORK
- **Ground Truth Locator:** NET-WIFI
- **Ground Truth Evidence:** RSSI 低于 -70 dBm 或同信道利用率超过 70% 时容易断开。优先调整 AP 位置和信道；不要通过提高所有 AP 发射功率掩盖漫游设计问题。
- **Reference Answer:** 不是；优先调整 AP 位置和信道，不应把所有 AP 功率都提高。
- **Why valuable:** 反事实问法。
- **Special flag:** `GENERAL_REPRESENTATIVE`
- **Human decision:** [ ] accept  [ ] revise  [ ] reject
- **Reviewer note:**

## 8. v2q039

- **Query:** 工单日志里带着同事邮箱和公网地址，可以原样上传吗？
- **Category:** `paraphrase_colloquial`
- **Answerable:** `true`
- **Ground Truth Document:** EVAL-SECURITY
- **Ground Truth Locator:** SEC-REDACT
- **Ground Truth Evidence:** 用于一般故障工单的日志必须掩码用户邮箱和公网 IP。涉及安全调查时可保留原值，但工单需标记“受限”并限定安全响应人员访问。
- **Reference Answer:** 一般故障工单不可以，必须掩码；安全调查需受限标记。
- **Why valuable:** 场景化规则。
- **Special flag:** `GENERAL_REPRESENTATIVE`
- **Human decision:** [ ] accept  [ ] revise  [ ] reject
- **Reviewer note:**

## 9. v2q047

- **Query:** A100 V1 的“配对”小节中，输错后暂停的是哪项入口？
- **Category:** `parent_context`
- **Answerable:** `true`
- **Ground Truth Document:** EVAL-A100-V1
- **Ground Truth Locator:** A100V1-PAIR
- **Ground Truth Evidence:** 管理员在终端输入六位配对码，配对码有效期 10 分钟。连续输入错误 5 次后，配对入口暂停 15 分钟，但设备本身不会退出已加入的会议。
- **Reference Answer:** 配对入口。
- **Why valuable:** 子标题需结合产品版本。
- **Special flag:** `PARENT_CONTEXT`
- **Human decision:** [ ] accept  [ ] revise  [ ] reject
- **Reviewer note:**

## 10. v2q051

- **Query:** 无线故障章节中的 N201 不是哪类故障？
- **Category:** `parent_context`
- **Answerable:** `true`
- **Ground Truth Document:** EVAL-NETWORK
- **Ground Truth Locator:** NET-CODE-N201
- **Ground Truth Evidence:** N201 表示 DHCP 在 60 秒内未分配地址。检查 VLAN、地址池余量和 DHCP Relay。它不表示 DNS 故障。
- **Reference Answer:** 不是 DNS 故障。
- **Why valuable:** 相似错误码干扰。
- **Special flag:** `PARENT_CONTEXT / ERROR-CODE CONFUSION`
- **Human decision:** [ ] accept  [ ] revise  [ ] reject
- **Reviewer note:**

## 11. v2q056

- **Query:** 运维手册的证据采集章节要求故障前后各覆盖多久？
- **Category:** `parent_context`
- **Answerable:** `true`
- **Ground Truth Document:** EVAL-OPS
- **Ground Truth Locator:** OPS-LOGS
- **Ground Truth Evidence:** 采集时间范围应覆盖故障前后各 15 分钟，记录终端序列号、站点、会议 ID、网络路径和时钟偏差。普通工单上传前必须按安全规范脱敏。
- **Reference Answer:** 各 15 分钟。
- **Why valuable:** 通用数值需父语境。
- **Special flag:** `GENERAL_REPRESENTATIVE`
- **Human decision:** [ ] accept  [ ] revise  [ ] reject
- **Reviewer note:**

## 12. v2q059

- **Query:** A100 V1 和 V2 的供电方式分别是什么？
- **Category:** `version_confusion`
- **Answerable:** `true`
- **Ground Truth Document:** EVAL-A100-V1, EVAL-A100-V2
- **Ground Truth Locator:** A100V1-POWER, A100V2-POWER
- **Ground Truth Evidence:** A100 V1 使用 12 V/3 A 圆口适配器。通电后状态灯先呈白色约 40 秒，完成启动后转为绿色。安装时应在设备两侧各保留至少 8 cm 散热空间，不得放入封闭抽屉。 | A100 V2 使用 USB-C PD 45 W 供电。正常启动约需 25 秒，指示灯由紫色呼吸转为绿色常亮。设备两侧各保留 5 cm 即可，但顶部散热孔不得覆盖。
- **Reference Answer:** V1 为 12 V/3 A 圆口；V2 为 USB-C PD 45 W。
- **Why valuable:** 同型号跨版本。
- **Special flag:** `VERSION_CONFUSION`
- **Human decision:** [ ] accept  [ ] revise  [ ] reject
- **Reviewer note:**

## 13. v2q062

- **Query:** A100 V2 的 U103 能按 V1 的签名错误处理吗？
- **Category:** `version_confusion`
- **Answerable:** `true`
- **Ground Truth Document:** EVAL-A100-V1, EVAL-A100-V2
- **Ground Truth Locator:** A100V1-UPDATE, A100V2-UPDATE
- **Ground Truth Evidence:** V1 的升级包必须使用 `.a1u` 格式，通过“维护 > 本地升级”导入。升级过程中不得断电；失败代码 U103 表示升级包签名不适用于 A100-G1。 | V2 使用 `.a2u` 升级包，并支持 HTTPS 在线升级。错误 U103 在 V2 中表示可用存储空间不足 2 GB，而不是签名错误。
- **Reference Answer:** 不能；V2 表示空间不足 2 GB，V1 才表示签名不匹配。
- **Why valuable:** 同错误码异义。
- **Special flag:** `VERSION_CONFUSION / SAME ERROR CODE`
- **Human decision:** [ ] accept  [ ] revise  [ ] reject
- **Reviewer note:**

## 14. v2q065

- **Query:** A100 V1、V2、A200 的离线升级包分别是什么？
- **Category:** `version_confusion`
- **Answerable:** `true`
- **Ground Truth Document:** EVAL-A100-V1, EVAL-A100-V2, EVAL-A200
- **Ground Truth Locator:** A100V1-UPDATE, A100V2-UPDATE, A200-UPDATE
- **Ground Truth Evidence:** V1 的升级包必须使用 `.a1u` 格式，通过“维护 > 本地升级”导入。升级过程中不得断电；失败代码 U103 表示升级包签名不适用于 A100-G1。 | V2 使用 `.a2u` 升级包，并支持 HTTPS 在线升级。错误 U103 在 V2 中表示可用存储空间不足 2 GB，而不是签名错误。 | A200 离线包扩展名为 `.a2k`。错误 U103 表示主备节点版本不一致，应先升级备用节点，再升级主节点。
- **Reference Answer:** 依次为 .a1u、.a2u、.a2k。
- **Why valuable:** 三文档包格式。
- **Special flag:** `VERSION_CONFUSION / THREE DOCUMENTS`
- **Human decision:** [ ] accept  [ ] revise  [ ] reject
- **Reviewer note:**

## 15. v2q070

- **Query:** U103 出现在 A200 上时，清理 2 GB 空间是否正确？
- **Category:** `version_confusion`
- **Answerable:** `true`
- **Ground Truth Document:** EVAL-A100-V2, EVAL-A200
- **Ground Truth Locator:** A100V2-UPDATE, A200-UPDATE
- **Ground Truth Evidence:** V2 使用 `.a2u` 升级包，并支持 HTTPS 在线升级。错误 U103 在 V2 中表示可用存储空间不足 2 GB，而不是签名错误。 | A200 离线包扩展名为 `.a2k`。错误 U103 表示主备节点版本不一致，应先升级备用节点，再升级主节点。
- **Reference Answer:** 不正确；A200 的 U103 是主备版本不一致，空间不足 2 GB 是 A100 V2 的含义。
- **Why valuable:** 错误码干扰。
- **Special flag:** `VERSION_CONFUSION / SAME ERROR CODE`
- **Human decision:** [ ] accept  [ ] revise  [ ] reject
- **Reviewer note:**

## 16. v2q071

- **Query:** 部署一台 A100 V2 做 4K 会议，需要预留多少带宽且设备侧还需满足什么录制条件？
- **Category:** `multi_document`
- **Answerable:** `true`
- **Ground Truth Document:** EVAL-A100-V2, EVAL-DEPLOY
- **Ground Truth Locator:** DEPLOY-BANDWIDTH, A100V2-MEETING
- **Ground Truth Evidence:** 单台终端的推荐预留带宽如下。数字是双向可用带宽，不是月度流量。 | 模式 | A100 V1 | A100 V2 | A200 | |---|---:|---:|---:| | 720p | 2 Mbps | 2 Mbps | 3 Mbps | | 1080p | 4 Mbps | 4 Mbps | 6 Mbps | | 双屏/4K | 不支持 | 12 Mbps | 16 Mbps | | A100 V2 单场会议最多显示 16 路视频画面，可保存 50 个常用会议室。在插入通过兼容性认证的 USB 3.0 存储设备后，可启用本地 4K 录制。
- **Reference Answer:** 预留双向 12 Mbps；本地录制还需兼容的 USB 3.0 存储设备。
- **Why valuable:** 部署表与产品手册组合。
- **Special flag:** `MULTI_DOCUMENT / TABLE`
- **Human decision:** [ ] accept  [ ] revise  [ ] reject
- **Reviewer note:**

## 17. v2q074

- **Query:** 普通故障工单采集日志时，时间范围和隐私处理分别怎么做？
- **Category:** `multi_document`
- **Answerable:** `true`
- **Ground Truth Document:** EVAL-OPS, EVAL-SECURITY
- **Ground Truth Locator:** OPS-LOGS, SEC-REDACT
- **Ground Truth Evidence:** 采集时间范围应覆盖故障前后各 15 分钟，记录终端序列号、站点、会议 ID、网络路径和时钟偏差。普通工单上传前必须按安全规范脱敏。 | 用于一般故障工单的日志必须掩码用户邮箱和公网 IP。涉及安全调查时可保留原值，但工单需标记“受限”并限定安全响应人员访问。
- **Reference Answer:** 覆盖故障前后各 15 分钟，并掩码邮箱和公网 IP。
- **Why valuable:** 跨运维与安全规范。
- **Special flag:** `MULTI_DOCUMENT`
- **Human decision:** [ ] accept  [ ] revise  [ ] reject
- **Reviewer note:**

## 18. v2q078

- **Query:** 组织管理员导出全量审计日志需要什么审批，下载包又有什么限制？
- **Category:** `multi_document`
- **Answerable:** `true`
- **Ground Truth Document:** EVAL-ACCOUNT, EVAL-SECURITY
- **Ground Truth Locator:** ACC-EXPORT, SEC-EXPORT
- **Ground Truth Evidence:** 导出全量成员列表需要组织管理员发起并由审计员批准。站点管理员只能导出本授权站点的成员摘要。 | 全量审计日志导出需要组织管理员发起、审计员批准。导出包有效期 24 小时，下载链接最多使用 3 次。
- **Reference Answer:** 组织管理员发起、审计员批准；导出包 24 小时有效且最多下载 3 次。
- **Why valuable:** 权限和数据规则。
- **Special flag:** `MULTI_DOCUMENT / GOVERNANCE`
- **Human decision:** [ ] accept  [ ] revise  [ ] reject
- **Reviewer note:**

## 19. v2q081

- **Query:** A100 V2 跑双屏或 4K 时建议预留多少双向带宽？
- **Category:** `table`
- **Answerable:** `true`
- **Ground Truth Document:** EVAL-DEPLOY
- **Ground Truth Locator:** DEPLOY-BANDWIDTH
- **Ground Truth Evidence:** 单台终端的推荐预留带宽如下。数字是双向可用带宽，不是月度流量。 | 模式 | A100 V1 | A100 V2 | A200 | |---|---:|---:|---:| | 720p | 2 Mbps | 2 Mbps | 3 Mbps | | 1080p | 4 Mbps | 4 Mbps | 6 Mbps | | 双屏/4K | 不支持 | 12 Mbps | 16 Mbps |
- **Reference Answer:** 12 Mbps。
- **Why valuable:** 表格单元格。
- **Special flag:** `TABLE`
- **Human decision:** [ ] accept  [ ] revise  [ ] reject
- **Reviewer note:**

## 20. v2q083

- **Query:** 实时媒体的协议、端口范围和方向分别是什么？
- **Category:** `table`
- **Answerable:** `true`
- **Ground Truth Document:** EVAL-DEPLOY
- **Ground Truth Locator:** DEPLOY-PORTS
- **Ground Truth Evidence:** | 用途 | 协议 | 端口 | 方向 | |---|---|---:|---| | 设备注册 | TCP | 443 | 出站 | | 会议信令 | TCP | 8443 | 出站 | | 实时媒体 | UDP | 30000-31999 | 双向 | | 时间同步 | UDP | 123 | 出站 |
- **Reference Answer:** UDP、30000-31999、双向。
- **Why valuable:** 多列表格。
- **Special flag:** `TABLE`
- **Human decision:** [ ] accept  [ ] revise  [ ] reject
- **Reviewer note:**

## 21. v2q086

- **Query:** 无线掉线时快速检查表禁止先做什么？
- **Category:** `table`
- **Answerable:** `true`
- **Ground Truth Document:** EVAL-OPS
- **Ground Truth Locator:** OPS-CHECKLIST
- **Ground Truth Evidence:** | 现象 | 首查项 | 禁止的第一动作 | |---|---|---| | 无法注册 | DNS、TCP 443、时间 | 恢复出厂 | | 能入会无媒体 | UDP 30000-31999、NAT | 更换账号 | | 无线掉线 | RSSI、信道利用率 | 提高全部 AP 功率 | | 升级失败 | 型号、包格式、空间 | 反复强制断电 |
- **Reference Answer:** 禁止先提高全部 AP 功率。
- **Why valuable:** 运维表。
- **Special flag:** `TABLE`
- **Human decision:** [ ] accept  [ ] revise  [ ] reject
- **Reviewer note:**

## 22. v2q089

- **Query:** A300 会议终端最多支持多少路视频？
- **Category:** `no_answer`
- **Answerable:** `false`
- **Ground Truth Document:** NONE
- **Ground Truth Locator:** NONE
- **Ground Truth Evidence:** NONE — negative query
- **Reference Answer:** 知识库没有 A300 型号信息，无法确定。
- **Why valuable:** 不存在的型号。
- **Special flag:** `NO_ANSWER / NONEXISTENT MODEL`
- **Human decision:** [ ] accept  [ ] revise  [ ] reject
- **Reviewer note:**

## 23. v2q094

- **Query:** S1 故障一定会在两小时内彻底解决吗？
- **Category:** `no_answer`
- **Answerable:** `false`
- **Ground Truth Document:** NONE
- **Ground Truth Locator:** NONE
- **Ground Truth Evidence:** NONE — negative query
- **Reference Answer:** 文档只有首次响应和更新频率，没有解决时限。
- **Why valuable:** 不可从 SLA 推断。
- **Special flag:** `NO_ANSWER / UNSUPPORTED ROOT CAUSE`
- **Human decision:** [ ] accept  [ ] revise  [ ] reject
- **Reviewer note:**

## 24. v2q103

- **Query:** P1 事件的根因分析必须在几天内完成？
- **Category:** `no_answer`
- **Answerable:** `false`
- **Ground Truth Document:** NONE
- **Ground Truth Locator:** NONE
- **Ground Truth Evidence:** NONE — negative query
- **Reference Answer:** 文档没有规定根因分析完成期限。
- **Why valuable:** 运维期限缺失。
- **Special flag:** `NO_ANSWER / MISSING DEADLINE`
- **Human decision:** [ ] accept  [ ] revise  [ ] reject
- **Reviewer note:**

## 25. v2q109

- **Query:** N305 是否由某个特定运营商网络导致？
- **Category:** `no_answer`
- **Answerable:** `false`
- **Ground Truth Document:** NONE
- **Ground Truth Locator:** NONE
- **Ground Truth Evidence:** NONE — negative query
- **Reference Answer:** N305 说明媒体 UDP 超时，无法据此确定运营商原因。
- **Why valuable:** 原因归因不足。
- **Special flag:** `NO_ANSWER / UNSUPPORTED PERFORMANCE NUMBER`
- **Human decision:** [ ] accept  [ ] revise  [ ] reject
- **Reviewer note:**
