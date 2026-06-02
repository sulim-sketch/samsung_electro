# generate_html_dashboard.py — 독립 실행형 HTML 대시보드 생성
import json
import sys
from pathlib import Path

import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).parent))
import config

START, END = "2024-06-01", "2026-05-31"
# blog_counts.csv는 config.EXCLUDE_KEYWORDS 기준으로 사전 생성된 파일을 사용

# ── 데이터 준비 ───────────────────────────────────────────────────
blog_df = pd.read_csv(config.PROCESSED_DIR / "blog_counts.csv", parse_dates=["date"])
full_idx = pd.date_range(START, END, freq="D")

df_stock = yf.download("009150.KS", start=START, end="2026-06-01",
                        auto_adjust=True, progress=False)
price = df_stock["Close"].squeeze().dropna()
price.index = price.index.tz_localize(None)
price = price.reindex(full_idx).ffill().round(2)

dates  = full_idx.strftime("%Y-%m-%d").tolist()
prices = [None if pd.isna(v) else float(v) for v in price.values]
counts = (
    blog_df.set_index("date")["count"]
    .reindex(pd.to_datetime(dates))
    .fillna(0).astype(int).tolist()
)
data_json = json.dumps({"dates": dates, "prices": prices, "counts": counts},
                        ensure_ascii=False)

# ── HTML 생성 ─────────────────────────────────────────────────────
html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>삼성전기 대시보드</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'Segoe UI',Malgun Gothic,sans-serif;background:#f5f7fa;color:#333}}
  .wrap{{max-width:1280px;margin:0 auto;padding:24px}}
  h1{{font-size:24px;font-weight:700;margin-bottom:4px}}
  .caption{{font-size:13px;color:#888;margin-bottom:20px}}
  .controls{{display:flex;align-items:center;gap:20px;background:#fff;padding:14px 20px;
             border-radius:10px;box-shadow:0 1px 4px rgba(0,0,0,.08);margin-bottom:18px;flex-wrap:wrap}}
  .ctrl{{display:flex;align-items:center;gap:8px}}
  .ctrl label{{font-size:13px;color:#555;white-space:nowrap}}
  input[type=date]{{border:1px solid #ddd;border-radius:6px;padding:6px 10px;font-size:13px;outline:none;cursor:pointer}}
  input[type=date]:focus{{border-color:#1f77b4}}
  .sep{{width:1px;height:30px;background:#e0e0e0}}
  .radios{{display:flex;gap:6px}}
  .radios label{{display:flex;align-items:center;gap:6px;cursor:pointer;padding:6px 14px;
                 border-radius:6px;font-size:13px;border:1px solid #ddd;background:#fafafa;transition:all .15s}}
  .radios input[type=radio]{{display:none}}
  .radios label.active{{background:#e8f0fb;border-color:#1f77b4;color:#1f77b4;font-weight:600}}
  .sources{{display:flex;gap:6px;align-items:center}}
  .sources .src-label{{display:flex;align-items:center;gap:6px;cursor:pointer;padding:6px 14px;
                        border-radius:6px;font-size:13px;border:1px solid #ddd;background:#fafafa;transition:all .15s}}
  .sources .src-label.active{{background:#e8f0fb;border-color:#1f77b4;color:#1f77b4;font-weight:600}}
  .src-title{{font-size:13px;color:#555;white-space:nowrap}}
  .metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:18px}}
  .card{{background:#fff;border-radius:10px;padding:16px 20px;box-shadow:0 1px 4px rgba(0,0,0,.08)}}
  .card .lbl{{font-size:12px;color:#888;margin-bottom:6px}}
  .card .val{{font-size:22px;font-weight:700}}
  .card .delta{{font-size:13px;margin-top:4px}}
  .pos{{color:#e05c5c}}.neg{{color:#1f77b4}}
  .chart-box{{background:#fff;border-radius:10px;box-shadow:0 1px 4px rgba(0,0,0,.08);padding:8px}}
</style>
</head>
<body>
<div class="wrap">
  <h1>📈 삼성전기 (009150) 대시보드</h1>
  <p class="caption" id="cap">수정주가 &amp; 네이버 블로그 추천 언급 빈도</p>

  <div class="controls">
    <div class="ctrl"><label>시작일</label>
      <input type="date" id="ds" value="2024-06-01" min="2024-06-01" max="2026-05-31"></div>
    <div class="ctrl"><label>종료일</label>
      <input type="date" id="de" value="2026-05-31" min="2024-06-01" max="2026-05-31"></div>
    <div class="sep"></div>
    <div class="ctrl">
      <span class="src-title">📡 데이터 소스</span>
      <div class="sources" id="sources">
        <label class="src-label active">
          <input type="checkbox" name="src" value="naver_blog" checked>
          <span>네이버 블로그</span>
        </label>
      </div>
    </div>
    <div class="sep"></div>
    <div class="radios" id="modeGroup">
      <label class="active"><input type="radio" name="mode" value="integrated" checked><span>통합 (이중 Y축)</span></label>
      <label><input type="radio" name="mode" value="split"><span>분리 (상단: 주가 / 하단: 언급 수)</span></label>
    </div>
  </div>

  <div class="metrics">
    <div class="card"><div class="lbl">조회 시작가</div><div class="val" id="m1">-</div></div>
    <div class="card"><div class="lbl">조회 종료가</div><div class="val" id="m2">-</div><div class="delta" id="md"></div></div>
    <div class="card"><div class="lbl">블로그 언급 총합</div><div class="val" id="m3">-</div></div>
    <div class="card"><div class="lbl">일 평균 언급</div><div class="val" id="m4">-</div></div>
  </div>

  <div class="chart-box"><div id="chart"></div></div>
</div>

<script>
var D = {data_json};
var CFG = {{displayModeBar:false,responsive:true}};

function slice(start,end){{
  var si=D.dates.indexOf(start), ei=D.dates.indexOf(end);
  if(si<0)si=0; if(ei<0)ei=D.dates.length-1;
  return{{dates:D.dates.slice(si,ei+1),prices:D.prices.slice(si,ei+1),counts:D.counts.slice(si,ei+1)}};
}}
function fv(a){{for(var i=0;i<a.length;i++)if(a[i]!=null)return a[i];return null;}}
function lv(a){{for(var i=a.length-1;i>=0;i--)if(a[i]!=null)return a[i];return null;}}
function pad(start,end){{
  var s=new Date(start),e=new Date(end),p=Math.round((e-s)/864e5*.1);
  var x=new Date(e);x.setDate(x.getDate()+p);return x.toISOString().slice(0,10);
}}
function ko(n){{return n==null?'N/A':Math.round(n).toLocaleString('ko-KR')+'원';}}

function updateMetrics(d){{
  var sp=fv(d.prices),ep=lv(d.prices);
  document.getElementById('m1').textContent=ko(sp);
  document.getElementById('m2').textContent=ko(ep);
  var el=document.getElementById('md');
  if(sp!=null&&ep!=null){{
    var diff=Math.round(ep-sp);
    el.textContent=(diff>=0?'+':'')+diff.toLocaleString('ko-KR')+'원';
    el.className='delta '+(diff>=0?'pos':'neg');
  }}else el.textContent='';
  var tot=d.counts.reduce(function(a,b){{return a+b;}},0);
  document.getElementById('m3').textContent=tot.toLocaleString('ko-KR')+'건';
  document.getElementById('m4').textContent=(tot/d.dates.length).toFixed(1)+'건';
}}

function draw(d,mode,start,end){{
  var xe=pad(start,end);
  var xax={{showgrid:true,gridcolor:'#e5e5e5',fixedrange:true,tickformat:'%Y-%m',dtick:'M1',range:[start,xe]}};
  var avg=d.counts.reduce(function(a,b){{return a+b;}},0)/d.dates.length;

  if(mode==='integrated'){{
    var traces=[
      {{x:d.dates,y:d.counts,type:'bar',name:'블로그 추천 언급',marker:{{color:'#5b9bd5'}},opacity:0.6,
        yaxis:'y',hovertemplate:'%{{x}}<br>언급 수: %{{y}}건<extra></extra>'}},
      {{x:d.dates,y:d.prices,type:'scatter',mode:'lines',name:'수정종가',
        line:{{color:'#d62728',width:1.8}},yaxis:'y2',
        hovertemplate:'%{{x}}<br>종가: %{{y:,.0f}}원<extra></extra>'}}
    ];
    var shapes=[],annos=[];
    if(avg>0){{
      shapes=[{{type:'line',xref:'paper',x0:0,x1:1,yref:'y',y0:avg,y1:avg,
                line:{{color:'gray',dash:'dash',width:1}}}}];
      annos=[{{xref:'paper',x:0,yref:'y',y:avg,text:'평균 '+avg.toFixed(1)+'건',
               showarrow:false,xanchor:'left',yanchor:'bottom',font:{{size:11,color:'gray'}}}}];
    }}
    Plotly.react('chart',traces,{{
      height:520,hovermode:'x unified',dragmode:false,
      plot_bgcolor:'white',paper_bgcolor:'white',
      legend:{{orientation:'h',y:1.06,x:0}},
      margin:{{t:30,b:60,l:70,r:80}},font:{{size:12}},
      xaxis:xax,
      yaxis:{{showgrid:true,gridcolor:'#e5e5e5',fixedrange:true,
              title:'블로그 언급 수 (건)',rangemode:'tozero',autorange:true}},
      yaxis2:{{showgrid:false,fixedrange:true,overlaying:'y',side:'right',
               title:'수정주가 (원)',autorange:true,tickformat:','}},
      shapes:shapes,annotations:annos
    }},CFG);
  }} else {{
    var traces=[
      {{x:d.dates,y:d.prices,type:'scatter',mode:'lines',name:'수정종가',
        line:{{color:'#1f77b4',width:1.5}},fill:'tozeroy',fillcolor:'rgba(31,119,180,0.07)',
        xaxis:'x2',yaxis:'y2',hovertemplate:'%{{x}}<br>종가: %{{y:,.0f}}원<extra></extra>'}},
      {{x:d.dates,y:d.counts,type:'bar',name:'블로그 추천 언급',marker:{{color:'#5b9bd5'}},
        xaxis:'x',yaxis:'y',hovertemplate:'%{{x}}<br>언급 수: %{{y}}건<extra></extra>'}}
    ];
    var x2ax=Object.assign({{}},xax,{{anchor:'y2',domain:[0,1]}});
    var x1ax=Object.assign({{}},xax,{{anchor:'y',domain:[0,1],matches:'x2'}});
    Plotly.react('chart',traces,{{
      height:580,hovermode:'x unified',dragmode:false,
      plot_bgcolor:'white',paper_bgcolor:'white',
      legend:{{orientation:'h',y:1.04,x:0}},
      margin:{{t:30,b:60,l:70,r:30}},font:{{size:12}},
      xaxis:x1ax, xaxis2:x2ax,
      yaxis:{{showgrid:true,gridcolor:'#e5e5e5',fixedrange:true,
              anchor:'x',domain:[0,0.32],rangemode:'tozero',autorange:true,title:'언급 수 (건)'}},
      yaxis2:{{showgrid:true,gridcolor:'#e5e5e5',fixedrange:true,
               anchor:'x2',domain:[0.42,1],autorange:true,title:'수정주가 (원)',tickformat:','}},
      annotations:[
        {{xref:'paper',yref:'paper',x:.5,y:1.02,text:'수정주가 (원)',showarrow:false,font:{{size:13}}}},
        {{xref:'paper',yref:'paper',x:.5,y:.30,text:'네이버 블로그 추천 언급 수 (건)',showarrow:false,font:{{size:13}}}}
      ]
    }},CFG);
  }}
}}

// 데이터 소스별 카운트 맵 (추후 소스 추가 시 여기에 등록)
var SOURCE_COUNTS = {{
  'naver_blog': D.counts
}};

function getActiveCounts(dates){{
  var active=document.querySelectorAll('input[name=src]:checked');
  var total=new Array(dates.length).fill(0);
  active.forEach(function(cb){{
    var src=SOURCE_COUNTS[cb.value];
    if(!src)return;
    for(var i=0;i<total.length;i++) total[i]+=src[i]||0;
  }});
  return total;
}}

function update(){{
  var start=document.getElementById('ds').value;
  var end=document.getElementById('de').value;
  if(start>end)return;
  var mode=document.querySelector('input[name=mode]:checked').value;
  var d=slice(start,end);
  d.counts=getActiveCounts(d.dates);  // 선택된 소스 합산
  document.getElementById('cap').textContent='수정주가 & 네이버 블로그 추천 언급 빈도 | '+start+' ~ '+end;
  updateMetrics(d);
  draw(d,mode,start,end);
  document.querySelectorAll('.radios label').forEach(function(l){{
    l.classList.toggle('active',l.querySelector('input').checked);
  }});
  document.querySelectorAll('.src-label').forEach(function(l){{
    l.classList.toggle('active',l.querySelector('input').checked);
  }});
}}

document.getElementById('ds').addEventListener('change',update);
document.getElementById('de').addEventListener('change',update);
document.querySelectorAll('input[name=mode]').forEach(function(r){{r.addEventListener('change',update);}});
document.querySelectorAll('input[name=src]').forEach(function(r){{r.addEventListener('change',update);}});
update();
</script>
</body>
</html>"""

out = config.PROCESSED_DIR / "dashboard.html"
out.write_text(html, encoding="utf-8")
print(f"저장 완료: {out}")
