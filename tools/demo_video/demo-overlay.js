// Editorial English presentation layer only. No records, policy, outputs or APIs are changed.
(() => {
  const translations = {
    '官方 Fare：未通知加价':'Official Fare: unnotified surge increase',
    '官方 No-show：政策待澄清':'Official No-show: policy clarification required',
    '官方 Route：超出 AI 权限':'Official Route: beyond AI authority',
    '真实模型调用的保存记录：展示这次运行结果；打开本页不会再次调用模型。':'Saved real model run. Opening this report does not call a model.',
    '这是事后记录，页面不执行退款。请同时展示原始检查与程序修正。':'Retained run record; no refund is executed. Inspect the original checks and program corrections together.',
    '返回演示目录':'Return to demo index',
    '检查原因与下一步':'Check explanations and next steps',
    '当前阻止发布的问题：':'Current publication blocker: ',
    '已保留的原始候选问题：':'Retained original candidate issue: ',
    '正常人工处理原因：':'Policy referral reason: ',
    '原论点：':'Original claim: ',
    '模型把必须澄清或由人工处理的问题标成了已解决，但现有材料不能解除这个限制。':'The model marked a required clarification or human gate as resolved. The supplied material cannot remove that restriction.',
    '继续保留人工或政策澄清出口，不能凭模型表态消除权限门槛。':'Keep the human or policy-clarification handoff. A model assertion cannot remove the authority gate.',
    '论点的引用类型不满足所选判断范围。记录了某人的说法，不等于证实了所述事件。':'The cited source type does not support this assessment scope. Recording a statement does not verify the alleged event.',
    '核对原论点的每个事实部分及原始记录，补齐相关依据或保留证据不足。':'Check each factual clause against original records. Supply relevant support or retain insufficient evidence.',
    '仍有影响裁决的证据、政策或输出检查问题，当前建议不能发布。':'Evidence, policy or output-check issues still affect this candidate; it cannot be released in that state.',
    '查看其他具体检查原因及待澄清事项。':'Inspect the specific check explanations and unresolved questions.',
    '政策与样例规则的关系尚未明确。':'The relationship between the policy and sample rules remains unclear.',
    '先确认适用规则，再决定是否能够自动处理。':'Clarify the applicable rule before deciding whether automated handling is possible.',
    '程序保守修正':'Conservative program corrections',
    '程序保留原输出，对不满足来源要求的论点降低支持评级，或按逐条评价修正汇总标签，然后重新检查全部规则。Fare 仅在政策条件及主依据独立成立时允许此修正；裁决与金额不变，未执行任何收费或退款。':'The program retains the original output, lowers unsupported argument ratings or reconciles summary labels, then reruns all checks. Fare corrections require independently established policy conditions and primary grounds. Decision and amount stay unchanged; no payment is executed.',
    '原始模型检查错误':'Original model check errors',
    '逐条修正记录':'Adjustment audit log',
    '原始 Judge 建议':'Original Judge proposal',
    '流程失败：尚无可采纳裁决':'Execution failed: no accepted ruling',
    '模型输出未通过检查':'Model output rejected by checks',
    '暂无可采纳的裁决依据。':'No accepted ruling grounds are available.',
    '客服／证据负责人':'Support / evidence owner',
    '该论点暂不能按已确认事实采用；不等于对方自动成立。':'This claim cannot be treated as a verified fact. It does not automatically validate the opposing claim.',
    '核对该论点所需记录，取得新材料后重建快照；如无法取得则保留缺失状态。':'Check the required records and rebuild the snapshot when new material arrives. Otherwise retain the gap.',
    '缺少裁决所需的关键材料。':'Material evidence needed for a decision is missing.',
    '确认材料来源并补充案卷，再重新分析。':'Verify provenance, supplement the case, then reassess.',
    '提供有来源的改道背景与额外收费依据核实记录；司机陈述本身不够。':'Provide sourced records of the detour context and extra-charge justification. The driver statement alone is insufficient.',
    '平台运营／证据负责人':'Platform operations / evidence owner',
    '决定改道是否有依据、额外收费是否成立。':'Affects whether the detour and extra charge are justified.',
    '由 Evidence 方补充可追溯记录、重建案卷快照，再重新运行分析。':'Add traceable records through Evidence, rebuild the snapshot, then rerun analysis.',
    '平台政策／数据负责人':'Platform policy / data owner',
    '影响关键政策或数据条件是否成立。':'Affects whether material policy or data conditions hold.',
    '提供权威政策或更正后的源数据；保留变更来源，重建快照后重跑，不能只修改 resolved 标签。':'Provide authoritative policy or corrected source data. Preserve provenance and rebuild the snapshot before rerunning; changing a resolved label is insufficient.',
    '人工复核负责人':'Human review owner',
    '官方政策规定本案必须由人工裁决；补齐材料不能免除该门槛。':'Official policy requires human adjudication. Supplementing evidence does not remove that gate.',
    '将当前证据、政策原文和双方陈述交人工审核；AI 仅整理材料，不据此自动裁决。':'Hand the current evidence, original policy and both positions to a human. AI organizes the material without an automatic ruling.',
    '定位本次输出检查中的错误码并修复对应模块输出。':'Locate the validation error codes and correct the responsible module output.',
    '集成／Judge 开发负责人':'Integration / Judge owner',
    '当前未产生可采纳的裁决输出。':'No accepted ruling was produced.',
    '修复失败步骤并运行回归测试，然后对同一案卷重新执行完整流程。':'Fix the failed step and run regression checks before rerunning the complete case workflow.',
    '案件处理与补充材料':'Case workbench and new information',
    '离线演示模式：新处理不调用云端模型；已有报告保留各自执行记录。':'Offline demonstration: new runs make no cloud-model calls. Imported reports retain their original execution records.',
    '真实模型模式：只有确认后的“处理”和“重新处理”会使用额度。':'Live mode: confirmed processing and reruns use model quota.',
    '我确认本次操作会调用模型并使用云端额度':'I confirm this operation will call models and use cloud quota',
    '页面刷新、查看报告、预览材料、登记人工结果均不调用模型。':'Browsing, previews and local human records do not call a model.',
    '下面读取实际执行记录。打开完整报告可查看双方观点和来源。':'Actual execution records. Open a report to inspect both perspectives and their sources.',
    '上传补充后的完整源数据 JSON。官方政策沿用原版本；此入口不能改写政策。每案最多补充一次，新旧记录都会保留。':'Upload the complete amended source JSON. Official policy stays pinned. One supplement round per case; both versions are preserved.',
    '预览只显示字面变化，不证明材料真实，也不能解除强制人工门槛。重新处理在启用真实模型时会消耗额度。':'Preview shows literal changes, not proof of authenticity. Mandatory human gates remain. Live reruns use quota.',
    '针对上面选择的待人工案件。本地登记不核验处理人身份，不执行退款，不覆盖 AI 建议，也不自动更新政策或先例。':'For the selected referred case. Local entry does not authenticate identity, execute refunds, overwrite the AI suggestion or update policy.',
    '谁提供了什么材料，补充了哪一条记录。合成演示请明确说明。':'Describe the source and change. Explicitly label synthetic demonstration material.',
    '1 · 开始处理':'1 · Start a case','2 · 案件进度':'2 · Case progress','3 · 补充材料并重新判断':'3 · Preview new information and rerun','4 · 登记人工处理结果':'4 · Record a human outcome',
    '选择等待人工／补材料的运行':'Select a run awaiting human review','选择案例':'Select case','处理所选案例':'Process selected case',
    '下载该案源数据 JSON':'Download source JSON','查看当前报告':'View current report','新的源数据 JSON':'Amended source JSON','材料来源':'Provenance',
    '团队合成演示材料':'Team-authored synthetic demonstration','用户提供，尚未独立核验':'User supplied; not independently verified','来源和修改说明':'Source and change note',
    '先预览，不调用模型':'Preview changes — no model call','确认这些变化并重新处理':'Confirm changes and rerun','预览结果':'Change preview',
    '退款金额（SGD）':'Refund amount (SGD)','人工决定':'Human decision','人工理由':'Reason for the decision','处理人':'Reviewer',
    '所依据的证据':'Supporting evidence','所依据的政策':'Policy references','保存人工记录':'Save human record','查看该案人工记录':'View human records',
    '打开完整报告':'Open full report','还没有运行记录。':'No runs yet.','流程完成':'Completed','待人工处理':'Awaiting human review','AI 建议':'AI suggestion','可补材料':'Supplement available','补材料轮次已用':'Supplement round used',
    '已登记人工结果；未执行退款。':'Human outcome recorded; no refund executed.','预览完成；尚未重跑。':'Preview complete. No rerun yet.','材料已修改，请重新预览。':'Input changed; preview again.',
    '已开始重新处理：':'Rerun started: ','已开始：':'Started: ','运行未完成：':'Run incomplete: ','未通过：':'Rejected: ',
    '争议证据与裁决工作台':'Dispute evidence and decision workbench',
    '案件证据与政策可逐条核对来源。运行模式见每个案件；离线结果不代表真实模型裁决。本页是一次运行的快照，切换案件不会发起模型请求。':'Inspect evidence and policy sources. This report is a saved snapshot; browsing does not call a model. Check each case\'s execution mode.',
    '主办方样例 · 非真实运营数据证明':'Organizer sample · not independently authenticated operational data',
    '用户补充材料 · 来源未独立核验':'Supplemented input · source not independently verified',
    '团队合成数据 · 绑定提供的 Ryde v2.1 政策':'Synthetic data · supplied Ryde v2.1 policy',
    '团队合成案例 · 政策也是合成规则':'Synthetic case · synthetic policy',
    '待人工复核':'Human review required','建议保留收费':'Suggest upholding the charge','建议全额退款':'Suggested full refund','建议部分退款':'Suggested partial refund',
    '流程失败／待恢复':'Execution failed / recovery needed','流程已完成':'Execution completed','执行状态与恢复':'Execution status and recovery','业务状态：':'Business status: ','；首次输出通过：':' · First output valid: ',
    '调用、复用与预算':'Calls, reuse and budget','限次修复记录（保留原始失败）':'Bounded repairs; original failures retained','推导复核结果（额外检查，不代表事实认证）':'Inference review; an extra check, not fact authentication','第二轮争议点与引用进展':'Response-round issues and citation progress',
    '流程进度':'Workflow progress','根据实际执行事件生成；静态报告是事后记录。':'Derived from actual execution events; this is a saved report.',
    '检查建议及其依据；本系统不执行收费或退款。':'Inspect the suggestion and its sources. This system does not execute charges or refunds.',
    '等待有来源的新材料或政策澄清；不能靠重复讨论消除缺口。':'Await sourced information or policy clarification. Repeated debate cannot remove the gap.',
    '政策要求人工处理；补充材料不能解除该权限门槛。':'Policy requires a human decision. Supplements cannot remove that authority gate.',
    '检查失败记录和预算，确认相同版本后续跑。':'Inspect failures and budgets before resuming with matching versions.',
    '本次结果':'Recommendation','退款金额：':'Refund amount: ','未裁定':'Undetermined','页面只展示建议，不执行收费或退款。':'Suggestion only; no charge or refund is executed.',
    '已记录的依据':'Recorded reasoning','查看最终 JSON':'Inspect final JSON','计算结果与待澄清问题':'Calculations and open questions',
    '算术结果与已明确的规则分开列出；未明示的收费条件仍需澄清。距离／差额不等于责任／退款。':'Calculations are separate from policy interpretation. A distance or amount does not establish liability or a refund.',
    'Judge 如何看双方观点':'How the Judge assesses both sides','以下为通过结构和引用检查的分析；这些检查不能证明自然语言推理正确。':'This analysis passed structural and reference checks; those checks do not prove the reasoning correct.',
    '当前是离线分析骨架：只列出需要判断的内容，尚未由模型评估双方观点。':'Offline analysis scaffold: issues to assess, not a live model assessment.',
    '本次没有通过检查的结构化分析，请查看复核原因和输出检查。':'No accepted structured analysis. Inspect the review reasons and validation.',
    '核心问题':'Decision question','乘客观点':'Rider position','司机观点':'Driver position','涉及论点：':'Arguments: ','依据：':'Sources: ',
    '逐条论点评估':'Claim-by-claim assessment','裁决关键条件':'Decision conditions','争议点分析':'Disputed issues','复核问题逐项处理':'Review issue responses','仍需补充的信息':'Missing information',
    '支持记录：':'Supporting records: ','反驳记录：':'Opposing records: ','政策：':'Policy: ','待补充：':'Missing: ','未引用':'Not cited','未列出':'None listed','无':'None',
    '本次分析未列出额外缺失信息。':'No additional missing information was listed.',
    '有依据支持':'Supported','部分有依据支持':'Partly supported','依据不足':'Insufficient support','有反证':'Contradicted','尚待判断':'Unresolved','有支持':'Supported','部分支持':'Partly supported','缺少支持证据':'Insufficient evidence','程序请求／非事实主张':'Procedural request / non-factual claim',
    '双方陈述与回应':'Advocate openings and responses','offline_placeholder 只摘录已有陈述，不代表已完成真实 Agent 辩论。':'In offline_placeholder mode, only existing statements are quoted; no real Agent debate has run.',
    '乘客 Advocate':'Rider Advocate','司机 Advocate':'Driver Advocate','第一轮陈述':'Opening argument','回应对方':'Response to the other side','未执行／输出被拒绝。':'Not executed / output rejected.',
    '证据与原文':'Evidence and source excerpts','点击编号或展开条目查看本次快照的原始记录。':'Click an identifier or expand an item to inspect its original source.',
    '政策与原文':'Policy and source excerpts','来源：':'Source: ','类型：':'Type: ','原文路径：':'Source path: ','通信日志':'Communication log','输出检查':'Output validation',
    '格式和编号有效，不等于模型理解正确。':'Valid structure and references do not prove correct interpretation.',
    '人工交接单':'Human handoff','由编排层生成的待办建议；未发送通知，也未自动执行操作。':'Suggested next steps from orchestration. No notifications or actions were executed.',
    '请主办方明确案内 8 分钟 no-show 阈值起算点，以及与 v2.1 §2.1 五分钟规则的关系和来源优先级。':'Ask the organizer to clarify the eight-minute threshold clock, its relationship to section 2.1 and source precedence.',
    '主办方／平台政策负责人':'Organizer / platform policy owner','免费等待起点已明确，但不足以决定争议收费条件。':'The free-wait start is defined, but disputed charging conditions remain unresolved.',
    '保留两份来源及缺失标记；收到可追溯的正式澄清后显式更新政策版本并重跑。':'Retain both sources and gaps. Update the policy version and rerun after traceable authoritative clarification.',
    '完成模型配置并评估真实 Judge 输出。':'Configure the provider and evaluate live Judge outputs.','Judge 开发负责人':'Judge owner','离线结果仅是分析骨架，尚未作出模型判断。':'Offline results are an analysis scaffold, not model decisions.',
    '用独立考题验证后显式开启 remote；记录模型版本与运行结果。':'Validate independently before enabling remote execution; record model version and results.',
    '提供当前快照的双方陈述与回应。':'Provide both openings and responses for the current snapshot.','Advocate 开发负责人':'Advocate owner','尚未运行真实双方辩论。':'No live advocate debate has run.','按现有接口或快照绑定 JSON 接入四份输出，再联调。':'Integrate all four outputs through the existing interface and snapshot-bound JSON.',
    '需要补充：':'Information needed: ','建议负责人：':'Suggested owner: ','影响：':'Decision impact: ','下一步：':'Next action: ',
    '规则来源':'Policy provenance','每条政策保留案卷中的来源标签；团队程序检查不代表平台收费政策。':'Policy retains its source label. Programmatic safeguards are not platform charging policy.','查看团队检查约定':'Inspect local safeguards',
    '本次绑定的政策与程序检查':'Bound policy and programmatic checks','人工审核门槛':'Mandatory human-review gates','逐项政策条件':'Policy conditions','来源、信心因素与分项动作':'Sources, confidence factors and actions',
    '先例对照':'Precedent comparison','相似点：':'Similarities: ','差异：':'Differences: ',
    '报告道路距离':'Reported road distance','参考':'Reference','差额（未裁定退款）':'difference (not a refund award)','原记录金额':'Recorded amount','（未裁定退款）':'(not a refund award)','采样路线':'Sampled route','政策免费等待':'Policy free-wait period','从预约时间起':'From scheduled pickup: ','分钟；结束：':'minutes; ends: ',
    '仅供提示':'Informational','需 Judge 分析':'Requires Judge analysis','必须补充政策或数据':'Policy or data clarification required','政策要求人工裁决':'Policy requires human adjudication','等待政策澄清':'Awaiting policy clarification','等待补充证据':'Awaiting evidence',
    '快照 ':'Snapshot ','运行 ':'Run ',' · 生效 ':' · Effective ',
    '准备证据':'Prepare evidence','检查政策':'Check policy','乘客开场':'Rider opening','司机开场':'Driver opening','乘客回应':'Rider response','司机回应':'Driver response','Judge 判断':'Judge decision','结果检查':'Output checks','推导复核':'Inference review','限次结构修复':'Bounded structural repair',
    '复用已有结果':'Reused output','未执行／不适用':'Skipped / not applicable','尚未执行':'Pending','进行中':'Running','流程失败':'Failed','流程中断':'Interrupted','处理中':'Running','排队中':'Queued','暂无可采纳结果':'No accepted result',
    '已处理':'Resolved','仍待澄清':'Unresolved','不满足':'Not met','满足':'Met','未知':'Unknown','未分类':'Unclassified','完成':'Completed','耗时未知':'Duration unknown','保留收费':'Uphold charge','部分退款':'Partial refund','全额退款':'Full refund',' 秒 / ':' seconds / ',' 分钟':' minutes',' / 差额 ':' / difference '
  };
  const entries = Object.entries(translations).sort((a,b)=>b[0].length-a[0].length);
  function translate(text){if(!/[\u3400-\u9fff]/.test(text))return text;for(const [a,b]of entries)text=text.split(a).join(b);return text;}
  function ready(){
    document.documentElement.lang='en';
    const style=document.createElement('style');style.textContent=`
      body:not(.demo-slides){font-size:20px!important;padding-bottom:180px!important;background:#eaf1f2!important;color:#19313e!important}
      body:not(.demo-slides) main{max-width:1640px!important;padding:116px 28px 200px!important}
      body:not(.demo-slides) h1{font-size:37px!important}body:not(.demo-slides) h2{font-size:31px!important}body:not(.demo-slides) h3{font-size:26px!important}body:not(.demo-slides) h4{font-size:22px!important}
      body:not(.demo-slides) pre{font-size:17px!important;line-height:1.5!important;max-height:460px!important}body:not(.demo-slides) .ref{font-size:17px!important}
      body:not(.demo-slides) section{padding:28px!important}body:not(.demo-slides) fieldset label{font-size:17px!important}
      section,details,[id]{scroll-margin-top:125px!important}html{scroll-padding-top:125px;scroll-behavior:smooth}
      #demo-top{position:fixed;z-index:2147483640;left:0;right:0;top:0;height:90px;display:flex;align-items:center;gap:36px;padding:0 56px;color:#eefafa;background:#071d29;font-family:'Segoe UI',sans-serif;box-shadow:0 5px 20px #071d2920;pointer-events:none}
      #demo-top strong{font-size:29px;letter-spacing:-1px}#demo-top strong span{color:#72e3cf}#demo-title{font-size:23px}#demo-chapter{font-size:12px;letter-spacing:3px;color:#80b7bd;margin-bottom:5px}#demo-badge{margin-left:auto;font-size:16px;color:#80e0d1;white-space:nowrap;border:1px solid #3a5b63;padding:9px 15px;border-radius:7px}
      #demo-bottom{position:fixed;z-index:2147483640;left:0;right:0;bottom:0;height:138px;background:#071d29;pointer-events:none}#demo-bottom span{position:absolute;left:36px;bottom:10px;font:12px 'Segoe UI',sans-serif;color:#789da5;letter-spacing:2px}
      #demo-pointer{position:fixed;width:32px;height:42px;left:-50px;top:-50px;pointer-events:none;z-index:2147483646;filter:drop-shadow(0 2px 4px #0006)}
      .demo-ripple{position:fixed;width:64px;height:64px;border:4px solid #13cbb0;background:#13cbb033;border-radius:50%;pointer-events:none;z-index:2147483645;animation:demoRipple .85s ease-out forwards}
      @keyframes demoRipple{from{transform:scale(.4);opacity:1}to{transform:scale(1.6);opacity:0}}
      .demo-focus{outline:4px solid #15bfa6!important;outline-offset:7px!important;border-radius:5px;transition:outline-color .2s}
      #demo-sync{position:fixed;left:0;top:0;width:32px;height:32px;background:#ff00ff;z-index:2147483647}
    `;document.head.append(style);
    if(document.querySelector('#slide'))document.body.classList.add('demo-slides');
    const top=document.createElement('div');top.id='demo-top';top.innerHTML='<strong>Ryde<span>Resolve</span></strong><div><div id="demo-chapter"></div><div id="demo-title"></div></div><div id="demo-badge"></div>';document.body.append(top);
    const bottom=document.createElement('div');bottom.id='demo-bottom';bottom.innerHTML='<span>ENGLISH DEMO VIEW · RECORDING 52e5b53</span>';document.body.append(bottom);
    const pointer=document.createElement('div');pointer.id='demo-pointer';pointer.innerHTML='<svg width="32" height="42" viewBox="0 0 32 42"><path d="M3 2 L3 31 L11 24 L18 38 L24 35 L17 22 L29 22 Z" fill="#fff" stroke="#073f46" stroke-width="2.5" stroke-linejoin="round"/></svg>';document.body.append(pointer);
    document.addEventListener('mousemove',e=>{pointer.style.left=e.clientX+'px';pointer.style.top=e.clientY+'px';});
    document.addEventListener('mousedown',e=>{const p=document.createElement('div');p.className='demo-ripple';p.style.left=e.clientX-32+'px';p.style.top=e.clientY-32+'px';document.body.append(p);setTimeout(()=>p.remove(),900);});
    window.demoScene=(scene)=>{document.querySelector('#demo-chapter').textContent=scene.chapter;document.querySelector('#demo-title').textContent=scene.title;document.querySelector('#demo-badge').textContent=scene.badge||'Hackathon prototype';document.querySelector('#demo-bottom span').textContent='ENGLISH DEMO VIEW · SOURCE '+(scene.source_commit||'52e5b53').slice(0,7);};
    let observing;
    const update=()=>{observing?.disconnect();const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);let node;while(node=walker.nextNode()){if(node.parentElement.closest('script,style,pre,#demo-top,#demo-bottom'))continue;const next=translate(node.nodeValue);if(next!==node.nodeValue)node.nodeValue=next;}document.querySelectorAll('[placeholder]').forEach(e=>e.placeholder=translate(e.placeholder));observing?.observe(document.body,{childList:true,subtree:true,characterData:true});};
    observing=new MutationObserver(update);update();
    window.demoUntranslated=()=>{const w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);let n,a=[];while(n=w.nextNode())if(!n.parentElement.closest('script,style,pre')&&/[\u3400-\u9fff]/.test(n.nodeValue))a.push(n.nodeValue.trim());return a;};
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',ready);else ready();
})();
