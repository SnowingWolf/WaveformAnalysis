export type PipelineStage = "records" | "threshold" | "merge" | "aggregate" | "features" | "pairs";

const descriptions: Record<PipelineStage, string> = {
  records: "采集文件解析为带时间、板卡和通道的 records 索引，索引指向 wave_pool 中的波形片段。",
  threshold: "扣除基线并按极性转换后的信号越过阈值，两个过阈区间标为 hit。",
  merge: "启用合并时，同板卡同通道且采样间隔相同的两个 hit，在间隔和总宽限制内合并。",
  aggregate: "三个板卡通道上的 hit 区间按时间窗口组成一个 peaklet，此处只聚合成员区间。",
  features: "成员波形对齐求和，再提取面积与时序特征，最后按用户配置分类。",
  pairs: "两个 S1 与一个 S2 形成候选，默认 largest 策略选中面积更大的 S1，未选候选仍保留。",
};

export function PipelineFigure({ stage }: { stage: PipelineStage }) {
  return <svg viewBox="0 0 240 144" role="img" aria-label={descriptions[stage]}>
    {stage === "records" && <>
      <text x="16" y="21">采集文件</text>
      <rect className="figure-area" x="16" y="34" width="53" height="67" rx="5" />
      <path className="figure-muted" d="M27 48H57M27 60H57M27 72H48M27 84H57" />
      <path d="M78 64H100M95 59L100 64L95 69" />
      <text x="112" y="21">records 索引</text>
      <rect className="figure-area" x="110" y="34" width="114" height="31" rx="4" />
      <text className="figure-mono" x="119" y="54">time · 0:0 · dt</text>
      <path className="figure-muted" d="M167 70V83M162 78L167 83L172 78" />
      <path d="M110 109H125L129 105L133 112L139 91L145 109H160L165 104L172 97L181 109H224" />
      <text className="figure-mono" x="134" y="134">wave_pool</text>
    </>}
    {stage === "threshold" && <>
      <text x="16" y="21">信号 − 基线（按极性转换）</text>
      <path className="figure-axis" d="M16 34V111H225M220 107L225 111L220 115" />
      <rect className="figure-area" x="65" y="39" width="25" height="72" />
      <rect className="figure-area" x="144" y="56" width="34" height="55" />
      <path className="figure-dashed" d="M16 77H225" />
      <text x="182" y="70">阈值</text>
      <path d="M18 110L27 108L36 112L47 109L57 104L65 77L73 42L80 52L90 77L98 109L112 111L124 108L135 102L144 77L156 58L168 61L178 77L189 107L201 111L213 108L224 110" />
      <path d="M65 118V122H90V118M144 118V122H178V118" />
      <text className="figure-mono" x="63" y="138">hit 1</text><text className="figure-mono" x="143" y="138">hit 2</text>
    </>}
    {stage === "merge" && <>
      <text x="16" y="17">同一通道 0:0 · 相同 dt</text>
      <path className="figure-axis" d="M16 81H225M220 77L225 81L220 85" />
      <rect className="figure-area" x="35" y="52" width="55" height="29" rx="3" />
      <rect className="figure-area" x="121" y="52" width="69" height="29" rx="3" />
      <text className="figure-mono" x="47" y="72">hit 1</text><text className="figure-mono" x="140" y="72">hit 2</text>
      <path className="figure-dashed" d="M90 48V39H121V48" />
      <text className="figure-small" x="94" y="35">间隔</text>
      <path className="figure-muted" d="M61 85V91M160 85V91" />
      <rect className="figure-area" x="35" y="94" width="155" height="20" rx="3" />
      <text className="figure-mono" x="69" y="109">merged hit</text>
      <text className="figure-small" x="24" y="136">启用合并时 · 间隔与总宽受配置限制</text>
    </>}
    {stage === "aggregate" && <>
      <text x="16" y="21">按绝对时间聚合成员区间</text>
      <rect className="figure-area" x="75" y="32" width="111" height="82" rx="4" />
      <path className="figure-axis" d="M47 49H225M47 77H225M47 105H225" />
      <text className="figure-mono" x="12" y="53">0:0</text><text className="figure-mono" x="12" y="81">0:1</text><text className="figure-mono" x="12" y="109">1:0</text>
      <rect className="figure-hit" x="76" y="43" width="48" height="12" rx="2" />
      <rect className="figure-hit" x="99" y="71" width="61" height="12" rx="2" />
      <rect className="figure-hit" x="135" y="99" width="50" height="12" rx="2" />
      <path d="M75 119V124H186V119" />
      <text className="figure-mono" x="99" y="139">peaklet</text>
    </>}
    {stage === "features" && <>
      <text x="16" y="21">成员波形对齐 → 求和</text>
      <path className="figure-axis" d="M16 91H225" />
      <path className="figure-muted" d="M16 91H59Q68 91 77 67Q84 46 92 71Q101 91 113 91H225M16 91H73Q85 91 98 63Q109 43 121 72Q132 91 154 91H225" />
      <path className="figure-area" d="M16 91H59Q69 91 78 65Q85 39 94 48Q103 29 114 49Q124 77 143 88L154 91H225Z" />
      <text className="figure-small" x="155" y="51">求和波形</text>
      <rect className="figure-area" x="16" y="112" width="54" height="24" rx="4" />
      <rect className="figure-area" x="94" y="112" width="54" height="24" rx="4" />
      <rect className="figure-area" x="172" y="112" width="54" height="24" rx="4" />
      <text x="29" y="128">特征</text><text x="107" y="128">配置</text><text x="185" y="128">分类</text>
      <path d="M76 124H87M83 120L87 124L83 128M154 124H165M161 120L165 124L161 128" />
    </>}
    {stage === "pairs" && <>
      <text x="16" y="21">候选 → 选择 → 事件</text>
      <path className="figure-dashed" d="M70 48L185 70" />
      <path d="M70 94L185 70M176 67L185 70L179 77" />
      <rect className="figure-area" x="16" y="34" width="54" height="27" rx="4" />
      <rect className="figure-area" x="16" y="80" width="54" height="27" rx="4" />
      <rect className="figure-area" x="185" y="56" width="39" height="27" rx="4" />
      <text className="figure-mono" x="27" y="52">S1 a</text><text className="figure-mono" x="27" y="98">S1 b</text><text className="figure-mono" x="194" y="74">S2</text>
      <text className="figure-small" x="91" y="45">候选保留</text>
      <text className="figure-mono" x="88" y="107">selected</text>
      <text className="figure-small" x="16" y="135">默认：每个 S2 选最大面积 S1</text>
    </>}
  </svg>;
}
