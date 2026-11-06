"""styles.xml / settings.xml generation."""

from __future__ import annotations

STYLES_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:docDefaults>
  <w:rPrDefault><w:rPr>
    <w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="宋体" w:cs="Times New Roman"/>
    <w:kern w:val="2"/><w:sz w:val="24"/><w:szCs w:val="24"/>
    <w:lang w:val="en-US" w:eastAsia="zh-CN" w:bidi="ar-SA"/>
  </w:rPr></w:rPrDefault>
  <w:pPrDefault><w:pPr>
    <w:widowControl w:val="0"/><w:autoSpaceDE w:val="0"/><w:autoSpaceDN w:val="0"/>
    <w:spacing w:line="312" w:lineRule="auto"/>
  </w:pPr></w:pPrDefault>
</w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal">
  <w:name w:val="Normal"/><w:qFormat/>
  <w:pPr><w:widowControl w:val="0"/><w:autoSpaceDE w:val="0"/><w:autoSpaceDN w:val="0"/>
    <w:spacing w:line="312" w:lineRule="auto"/></w:pPr>
  <w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="宋体" w:cs="Times New Roman"/>
    <w:kern w:val="2"/><w:sz w:val="24"/><w:szCs w:val="24"/>
    <w:lang w:val="en-US" w:eastAsia="zh-CN" w:bidi="ar-SA"/></w:rPr>
</w:style>
<w:style w:type="paragraph" w:styleId="Heading1">
  <w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>
  <w:pPr><w:keepNext/><w:keepLines/><w:pageBreakBefore/>
    <w:spacing w:after="100" w:afterLines="100" w:line="500" w:lineRule="exact"/>
    <w:jc w:val="center"/><w:outlineLvl w:val="0"/></w:pPr>
  <w:rPr><w:rFonts w:eastAsia="黑体" w:cs="Arial" w:hint="eastAsia"/><w:bCs/><w:kern w:val="36"/>
    <w:sz w:val="36"/><w:szCs w:val="36"/></w:rPr>
</w:style>
<w:style w:type="paragraph" w:styleId="Heading2">
  <w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>
  <w:pPr><w:keepNext/><w:keepLines/>
    <w:spacing w:before="50" w:beforeLines="50" w:after="50" w:afterLines="50" w:line="240" w:lineRule="auto"/>
    <w:outlineLvl w:val="1"/></w:pPr>
  <w:rPr><w:rFonts w:eastAsia="黑体" w:hint="eastAsia"/><w:sz w:val="30"/><w:szCs w:val="30"/></w:rPr>
</w:style>
<w:style w:type="paragraph" w:styleId="Heading3">
  <w:name w:val="heading 3"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>
  <w:pPr><w:keepNext/><w:keepLines/>
    <w:spacing w:before="50" w:beforeLines="50" w:after="50" w:afterLines="50" w:line="240" w:lineRule="auto"/>
    <w:outlineLvl w:val="2"/></w:pPr>
  <w:rPr><w:rFonts w:eastAsia="黑体" w:hint="eastAsia"/><w:bCs/><w:sz w:val="28"/><w:szCs w:val="28"/></w:rPr>
</w:style>
<w:style w:type="paragraph" w:styleId="Heading4">
  <w:name w:val="heading 4"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>
  <w:pPr><w:keepNext/><w:keepLines/>
    <w:spacing w:before="50" w:beforeLines="50" w:after="0" w:line="312" w:lineRule="auto"/>
    <w:ind w:firstLine="200" w:firstLineChars="200"/><w:outlineLvl w:val="3"/></w:pPr>
  <w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="宋体" w:hint="eastAsia"/>
    <w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr>
</w:style>
<w:style w:type="paragraph" w:styleId="BodyTextIndent">
  <w:name w:val="Body Text First Indent"/><w:basedOn w:val="Normal"/><w:qFormat/>
  <w:pPr><w:ind w:firstLine="200" w:firstLineChars="200"/><w:jc w:val="both"/></w:pPr>
  <w:rPr><w:snapToGrid w:val="0"/></w:rPr>
</w:style>
<w:style w:type="paragraph" w:styleId="FigureCaption">
  <w:name w:val="图表标题"/><w:basedOn w:val="Normal"/><w:qFormat/>
  <w:pPr><w:autoSpaceDE w:val="0"/><w:autoSpaceDN w:val="0"/>
    <w:spacing w:before="50" w:beforeLines="50" w:after="50" w:afterLines="50"/>
    <w:jc w:val="center"/></w:pPr>
  <w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="宋体" w:cs="Times New Roman"/>
    <w:snapToGrid w:val="0"/><w:sz w:val="21"/><w:szCs w:val="21"/>
    <w:lang w:val="en-US" w:eastAsia="zh-CN" w:bidi="ar-SA"/></w:rPr>
</w:style>
<w:style w:type="paragraph" w:styleId="TableText">
  <w:name w:val="表内文字"/><w:basedOn w:val="FigureCaption"/><w:qFormat/>
  <w:pPr><w:spacing w:before="0" w:beforeLines="0" w:after="0" w:afterLines="0" w:line="312" w:lineRule="auto"/>
    <w:jc w:val="left"/></w:pPr>
</w:style>
<w:style w:type="paragraph" w:styleId="Equation">
  <w:name w:val="居中公式"/><w:basedOn w:val="BodyTextIndent"/><w:qFormat/>
  <w:pPr><w:adjustRightInd w:val="0"/><w:snapToGrid w:val="0"/>
    <w:ind w:firstLine="0" w:firstLineChars="0"/><w:jc w:val="center"/>
    <w:tabs><w:tab w:val="center" w:pos="4252"/><w:tab w:val="right" w:pos="8786"/></w:tabs></w:pPr>
  <w:rPr><w:snapToGrid w:val="0"/></w:rPr>
</w:style>
<w:style w:type="paragraph" w:styleId="ReferenceEntry">
  <w:name w:val="参考文献"/><w:basedOn w:val="Normal"/><w:qFormat/>
  <w:pPr><w:ind w:left="600" w:hanging="600"/><w:jc w:val="left"/>
    <w:spacing w:line="312" w:lineRule="auto"/></w:pPr>
  <w:rPr><w:snapToGrid w:val="0"/></w:rPr>
</w:style>
<w:style w:type="paragraph" w:styleId="TOC1">
  <w:name w:val="toc 1"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>
  <w:pPr><w:tabs><w:tab w:val="right" w:leader="dot" w:pos="8786"/></w:tabs></w:pPr>
  <w:rPr><w:rFonts w:eastAsia="黑体" w:hint="eastAsia"/></w:rPr>
</w:style>
<w:style w:type="paragraph" w:styleId="TOC2">
  <w:name w:val="toc 2"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>
  <w:pPr><w:tabs><w:tab w:val="right" w:leader="dot" w:pos="8786"/></w:tabs>
    <w:ind w:firstLine="200" w:firstLineChars="200"/></w:pPr>
</w:style>
<w:style w:type="paragraph" w:styleId="TOC3">
  <w:name w:val="toc 3"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>
  <w:pPr><w:tabs><w:tab w:val="right" w:leader="dot" w:pos="8786"/></w:tabs>
    <w:ind w:firstLine="300" w:firstLineChars="300"/></w:pPr>
</w:style>
<w:style w:type="paragraph" w:styleId="Header">
  <w:name w:val="header"/><w:basedOn w:val="Normal"/><w:qFormat/>
  <w:pPr><w:pBdr><w:bottom w:val="thinThickSmallGap" w:color="auto" w:sz="12" w:space="1"/></w:pBdr>
    <w:snapToGrid w:val="0"/><w:spacing w:line="240" w:lineRule="auto"/>
    <w:jc w:val="center"/><w:outlineLvl w:val="9"/></w:pPr>
  <w:rPr><w:sz w:val="21"/><w:szCs w:val="21"/></w:rPr>
</w:style>
<w:style w:type="paragraph" w:styleId="Footer">
  <w:name w:val="footer"/><w:basedOn w:val="Normal"/><w:qFormat/>
  <w:pPr><w:tabs><w:tab w:val="center" w:pos="4153"/><w:tab w:val="right" w:pos="8306"/></w:tabs>
    <w:snapToGrid w:val="0"/><w:spacing w:line="240" w:lineRule="auto"/>
    <w:jc w:val="center"/></w:pPr>
  <w:rPr><w:sz w:val="21"/><w:szCs w:val="21"/></w:rPr>
</w:style>
<w:style w:type="paragraph" w:styleId="CodeBlock">
  <w:name w:val="代码块"/><w:basedOn w:val="Normal"/><w:qFormat/>
  <w:pPr><w:adjustRightInd w:val="0"/><w:snapToGrid w:val="0"/>
    <w:spacing w:before="0" w:after="0" w:line="240" w:lineRule="auto"/>
    <w:ind w:firstLine="0" w:firstLineChars="0" w:left="0"/><w:jc w:val="left"/></w:pPr>
  <w:rPr><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas" w:eastAsia="宋体" w:cs="Consolas"/>
    <w:sz w:val="21"/><w:szCs w:val="21"/></w:rPr>
</w:style>
<w:style w:type="paragraph" w:styleId="CoverLine">
  <w:name w:val="封面行"/><w:basedOn w:val="Normal"/><w:qFormat/>
  <w:pPr><w:spacing w:before="0" w:after="0" w:line="240" w:lineRule="auto"/><w:jc w:val="center"/></w:pPr>
  <w:rPr><w:snapToGrid w:val="0"/></w:rPr>
</w:style>
</w:styles>
"""

SETTINGS_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:zoom w:percent="100"/>
  <w:defaultTabStop w:val="420"/>
  <w:characterSpacingControl w:val="compressPunctuation"/>
  <w:updateFields w:val="true"/>
  <w:compat>
    <w:spaceForUL/>
    <w:balanceSingleByteDoubleByteWidth/>
    <w:doNotLeaveBackslashAlone/>
    <w:ulTrailSpace/>
    <w:doNotExpandShiftReturn/>
    <w:adjustLineHeightInTable/>
    <w:doNotWrapTextWithPunct/>
    <w:doNotUseEastAsianBreakRules/>
    <w:useFELayout/>
    <w:useNormalStyleForList/>
    <w:doNotUseIndentAsNumberingTabStop/>
    <w:useAltKinsokuLineBreakRules/>
    <w:allowSpaceOfSameStyleInTable/>
    <w:doNotSuppressIndentation/>
    <w:doNotAutofitConstrainedTables/>
    <w:autofitToFirstFixedWidthCell/>
    <w:displayHangulFixedWidth/>
    <w:splitPgBreakAndParaMark/>
    <w:doNotVertAlignCellWithSp/>
    <w:doNotBreakConstrainedForcedTable/>
    <w:doNotVertAlignInTxbx/>
    <w:useAnsiKerningPairs/>
    <w:cachedColBalance/>
    <w:compatSetting w:name="compatibilityMode" w:uri="http://schemas.microsoft.com/office/word" w:val="11"/>
  </w:compat>
  <w:mathPr>
    <w:mathFont w:val="Cambria Math"/>
    <w:brkBin w:val="before"/><w:brkBinSub w:val="--"/>
    <w:smallFrac w:val="0"/><w:dispDef/>
    <w:lMargin w:val="0"/><w:rMargin w:val="0"/>
    <w:defJc w:val="centerGroup"/>
    <w:wrap w:val="inline"/>
    <w:intLim w:val="subSup"/><w:naryLim w:val="undOvr"/>
  </w:mathPr>
  <w:themeFontLang w:val="en-US" w:eastAsia="zh-CN"/>
</w:settings>
"""
