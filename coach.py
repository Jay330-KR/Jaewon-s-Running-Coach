from datetime import datetime, timedelta, timezone
import os

# 1. 가상 서버가 전 세계 어디에 있든 칼같이 한국 시간(KST)으로 고정
kst = timezone(timedelta(hours=9))
now_dt = datetime.now(timezone.utc).astimezone(kst)
now = now_dt.strftime("%Y-%m-%d %H:%M:%S")
today_date = now_dt.strftime("%Y-%m-%d")

readme_text = f"""# 🏃‍♂️ Project 330
> **Last Sync:** {now}

## 📈 Monthly Mileage (May)
🟠🟠🟠🟠🟠🟠🟠🟠🟠🟤🟤🟤🟤🟤🟤 **121.5** / 200 km (60%)

![May Daily Chart](https://quickchart.io/chart?c=%7B%27type%27%3A%20%27bar%27%2C%20%27data%27%3A%20%7B%27labels%27%3A%20%5B%271%27%2C%20%272%27%2C%20%273%27%2C%20%274%27%2C%20%275%27%2C%20%276%27%2C%20%277%27%2C%20%278%27%2C%20%279%27%2C%20%2710%27%2C%20%2711%27%2C%20%2712%27%2C%20%2713%27%2C%20%2714%27%2C%20%2715%27%2C%20%2716%27%2C%20%2717%27%2C%20%2718%27%2C%20%2719%27%2C%20%2720%27%2C%20%2721%27%2C%20%2722%27%2C%20%2723%27%2C%20%2724%27%2C%20%2725%27%2C%20%2726%27%2C%20%2727%27%2C%20%2728%27%2C%20%2729%27%2C%20%2730%27%2C%20%2731%27%5D%2C%20%27datasets%27%3A%20%5B%7B%27data%27%3A%20%5B8.31%2C%207.0%2C%209.0%2C%205.0%2C%2011.42%2C%205.08%2C%200.0%2C%208.74%2C%200.0%2C%2012.82%2C%2010.63%2C%205.39%2C%200.0%2C%208.82%2C%2010.03%2C%200.0%2C%2012.67%2C%200.0%2C%206.58%2C%200.0%2C%200.0%2C%200.0%2C%200.0%2C%200.0%2C%200.0%2C%200.0%2C%200.0%2C%200.0%2C%200.0%2C%200.0%2C%200.0%5D%2C%20%27backgroundColor%27%3A%20%27%23FC4C02%27%2C%20%27borderRadius%27%3A%204%2C%20%27datalabels%27%3A%20%7B%27display%27%3A%20false%7D%7D%5D%7D%2C%20%27options%27%3A%20%7B%27title%27%3A%20%7B%27display%27%3A%20false%7D%2C%20%27legend%27%3A%20%7B%27display%27%3A%20false%7D%2C%20%27scales%27%3A%20%7B%27yAxes%27%3A%20%5B%7B%27ticks%27%3A%20%7B%27beginAtZero%27%3A%20true%2C%20%27max%27%3A%2018%2C%20%27stepSize%27%3A%206%2C%20%27fontColor%27%3A%20%27%23888888%27%7D%2C%20%27gridLines%27%3A%20%7B%27color%27%3A%20%27rgba%28252%2C%2076%2C%202%2C%200.15%29%27%2C%20%27zeroLineColor%27%3A%20%27rgba%28252%2C%2076%2C%202%2C%200.3%29%27%7D%7D%5D%2C%20%27xAxes%27%3A%20%5B%7B%27ticks%27%3A%20%7B%27fontColor%27%3A%20%27%23888888%27%2C%20%27fontSize%27%3A%209%7D%2C%20%27gridLines%27%3A%20%7B%27display%27%3A%20false%7D%7D%5D%7D%2C%20%27plugins%27%3A%20%7B%27datalabels%27%3A%20false%7D%7D%7D&format=svg)

## ⏱️ Weekly Mileage
🟠🟤🟤🟤🟤🟤🟤🟤🟤🟤🟤🟤🟤🟤🟤 **6.6** / 50 km (13%)

![Weekly Chart](https://quickchart.io/chart?c=%7B%27type%27%3A%20%27bar%27%2C%20%27data%27%3A%20%7B%27labels%27%3A%20%5B%27Mon%27%2C%20%27Tue%27%2C%20%27Wed%27%2C%20%27Thu%27%2C%20%27Fri%27%2C%20%27Sat%27%2C%20%27Sun%27%5D%2C%20%27datasets%27%3A%20%5B%7B%27data%27%3A%20%5B0.0%2C%206.58%2C%200.0%2C%200.0%2C%200.0%2C%200.0%2C%200.0%5D%2C%20%27backgroundColor%27%3A%20%27%23FC4C02%27%2C%20%27borderRadius%27%3A%205%2C%20%27datalabels%27%3A%20%7B%27display%27%3A%20true%2C%20%27align%27%3A%20%27end%27%2C%20%27anchor%27%3A%20%27end%27%2C%20%27color%27%3A%20%27%23FC4C02%27%2C%20%27font%27%3A%20%7B%27weight%27%3A%20%27bold%27%2C%20%27size%27%3A%209%7D%7D%7D%5D%7D%2C%20%27options%27%3A%20%7B%27title%27%3A%20%7B%27display%27%3A%20false%7D%2C%20%27legend%27%3A%20%7B%27display%27%3A%20false%7D%2C%20%27scales%27%3A%20%7B%27yAxes%27%3A%20%5B%7B%27ticks%27%3A%20%7B%27beginAtZero%27%3A%20true%2C%20%27max%27%3A%2020%2C%20%27stepSize%27%3A%205%2C%20%27fontColor%27%3A%20%27%23888888%27%7D%2C%20%27gridLines%27%3A%20%7B%27color%27%3A%20%27rgba%28252%2C%2076%2C%202%2C%200.2%29%27%2C%20%27zeroLineColor%27%3A%20%27rgba%28252%2C%2076%2C%202%2C%200.4%29%27%7D%7D%5D%2C%20%27xAxes%27%3A%20%5B%7B%27ticks%27%3A%20%7B%27fontColor%27%3A%20%27%23888888%27%2C%20%27fontSize%27%3A%2011%2C%20%27fontStyle%27%3A%20%27bold%27%7D%2C%20%27gridLines%27%3A%20%7B%27display%27%3A%20false%7D%7D%5D%7D%2C%20%27plugins%27%3A%20%7B%27datalabels%27%3A%20false%7D%7D%7D&format=svg)

---

## 📊 Daily Running ({today_date})
* **Name:** No Run Today
* **Distance:** 💤 Rest Day
* **Pace(avg.):** -
* **Intensity:** **None (Rest Day)**

### 📋 Coach’s Comment
> 오늘은 온전한 휴식을 취하며 근육을 재건하고 코어 보강 운동에 집중하는 날입니다. 부상 방지를 위해 휴식도 훈련의 일부입니다.

### 🔮 Next Running
🏃‍♂️ **Next Target:** 5~7km 가벼운 빌드업 조깅 (목표 심박수: 140대)

---

## 🛠 Routine For Today
### 🎯 Objective: Core & Lower Body Reconstruction Routine

* 🔲 **[Step 1] Pre-Run Mobility Warmup**
  * 90/90 Stretching (5 reps L/R, hold 10s)
  * Hip Chair Circles (15 reps L/R)
  * Toe Yoga / Foot Core (10 reps x 3 sets)

* 🔲 **[Step 2] Post-Run Strength & Recovery Routine**
  * Deadbug (10 reps x 3 sets)
  * Side Plank + Clamshell (12 reps x 3 sets)
  * Romanian Deadlift 12kg (12 reps x 3 sets)
  * Split Squat 4kg (8 reps L/R x 3 sets)
"""

with open("README.md", "w", encoding="utf-8") as f:
    f.write(readme_text)

html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Project 330 Dashboard</title>
    <style>
        body {{ font-family: -apple-system, sans-serif; background-color: #121212; color: #e0e0e0; margin:0; padding:16px; }}
        .container {{ max-width: 500px; margin: 0 auto; background: #1e1e1e; padding: 20px; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.5); }}
        h1 {{ color: #FC4C02; text-align: center; font-size: 24px; }}
        h2 {{ color: #fff; border-bottom: 1px solid #333; padding-bottom: 6px; font-size: 18px; margin-top: 25px; }}
        h3 {{ color: #FC4C02; font-size: 15px; margin-top: 15px; }}
        blockquote {{ background: #2a2a2a; border-left: 4px solid #FC4C02; margin: 15px 0; padding: 12px; border-radius: 4px; font-style: italic; }}
        hr {{ border: 0; height: 1px; background: #333; margin: 20px 0; }}
        .chart-box {{ text-align: center; margin: 15px 0; background: #252525; padding: 10px; border-radius: 12px; }}
        .chart-box img {{ max-width: 100%; height: auto; }}
        ul {{ padding-left: 15px; }}
        li {{ margin-bottom: 8px; }}
        footer {{ text-align: center; font-size: 11px; color: #555; margin-top: 30px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🏃‍♂️ Project 330 Dashboard</h1>
        <p style="text-align:center; color:#888;">⏱️ Last Sync: {now}</p>
        <hr>
        <h2>📈 Monthly Mileage (May)</h2>
        <p>🟠🟠🟠🟠🟠🟠🟠🟠🟠🟤🟤🟤🟤🟤🟤 <strong>121.5</strong> / 200 km (60%)</p>
        <div class="chart-box"><img src="https://quickchart.io/chart?c=%7B%27type%27%3A%20%27bar%27%2C%20%27data%27%3A%20%7B%27labels%27%3A%20%5B%271%27%2C%20%272%27%2C%20%273%27%2C%20%274%27%2C%20%275%27%2C%20%276%27%2C%20%277%27%2C%20%278%27%2C%20%279%27%2C%20%2710%27%2C%20%2711%27%2C%20%2712%27%2C%20%2713%27%2C%20%2714%27%2C%20%2715%27%2C%20%2716%27%2C%20%2717%27%2C%20%2718%27%2C%20%2719%27%2C%20%2720%27%2C%20%2721%27%2C%20%2722%27%2C%20%2723%27%2C%20%2724%27%2C%20%2725%27%2C%20%2726%27%2C%20%2727%27%2C%20%2728%27%2C%20%2729%27%2C%20%2730%27%2C%20%2731%27%5D%2C%20%27datasets%27%3A%20%5B%7B%27data%27%3A%20%5B8.31%2C%207.0%2C%209.0%2C%205.0%2C%2011.42%2C%205.08%2C%200.0%2C%208.74%2C%200.0%2C%2012.82%2C%2010.63%2C%205.39%2C%200.0%2C%208.82%2C%2010.03%2C%200.0%2C%2012.67%2C%200.0%2C%206.58%2C%200.0%2C%200.0%2C%200.0%2C%200.0%2C%200.0%2C%200.0%2C%200.0%2C%200.0%2C%200.0%2C%200.0%2C%200.0%2C%200.0%5D%2C%20%27backgroundColor%27%3A%20%27%23FC4C02%27%2C%20%27borderRadius%27%3A%204%2C%20%27datalabels%27%3A%20%7B%27display%27%3A%20false%7D%7D%5D%7D%2C%20%27options%27%3A%20%7B%27title%27%3A%20%7B%27display%27%3A%20false%7D%2C%20%27legend%27%3A%20%7B%27display%27%3A%20false%7D%2C%20%27scales%27%3A%20%7B%27yAxes%27%3A%20%5B%7B%27ticks%27%3A%20%7B%27beginAtZero%27%3A%20true%2C%20%27max%27%3A%2018%2C%20%27stepSize%27%3A%206%2C%20%27fontColor%27%3A%20%27%23888888%27%7D%2C%20%27gridLines%27%3A%20%7B%27color%27%3A%20%27rgba%28252%2C%2076%2C%202%2C%200.15%29%27%2C%20%27zeroLineColor%27%3A%20%27rgba%28252%2C%2076%2C%202%2C%200.3%29%27%7D%7D%5D%2C%20%27xAxes%27%3A%20%5B%7B%27ticks%27%3A%20%7B%27fontColor%27%3A%20%27%23888888%27%2C%20%27fontSize%27%3A%209%7D%2C%20%27gridLines%27%3A%20%7B%27display%27%3A%20false%7D%7D%5D%7D%2C%20%27plugins%27%3A%20%7B%27datalabels%27%3A%20false%7D%7D%7D&format=svg" /></div>
        
        <h2>⏱️ Weekly Mileage</h2>
        <p>🟠🟤🟤🟤🟤🟤🟤🟤🟤🟤🟤🟤🟤🟤🟤 <strong>6.6</strong> / 50 km (13%)</p>
        <div class="chart-box"><img src="https://quickchart.io/chart?c=%7B%27type%27%3A%20%27bar%27%2C%20%27data%27%3A%20%7B%27labels%27%3A%20%5B%27Mon%27%2C%20%27Tue%27%2C%20%27Wed%27%2C%20%27Thu%27%2C%20%27Fri%27%2C%20%27Sat%27%2C%20%27Sun%27%5D%2C%20%27datasets%27%3A%20%5B%7B%27data%27%3A%20%5B0.0%2C%206.58%2C%200.0%2C%200.0%2C%200.0%2C%200.0%2C%200.0%5D%2C%20%27backgroundColor%27%3A%20%27%23FC4C02%27%2C%20%27borderRadius%27%3A%205%2C%20%27datalabels%27%3A%20%7B%27display%27%3A%20true%2C%20%27align%27%3A%20%27end%27%2C%20%27anchor%27%3A%20%27end%27%2C%20%27color%27%3A%20%27%23FC4C02%27%2C%20%27font%27%3A%20%7B%27weight%27%3A%20%27bold%27%2C%20%27size%27%3A%209%7D%7D%7D%5D%7D%2C%20%27options%27%3A%20%7B%27title%27%3A%20%7B%27display%27%3A%20false%7D%2C%20%27legend%27%3A%20%7B%27display%27%3A%20false%7D%2C%20%27scales%27%3A%20%7B%27yAxes%27%3A%20%5B%7B%27ticks%27%3A%20%7B%27beginAtZero%27%3A%20true%2C%20%27max%27%3A%2020%2C%20%27stepSize%27%3A%205%2C%20%27fontColor%27%3A%20%27%23888888%27%7D%2C%20%27gridLines%27%3A%20%7B%27color%27%3A%20%27rgba%28252%2C%2076%2C%202%2C%200.2%29%27%2C%20%27zeroLineColor%27%3A%20%27rgba%28252%2C%2076%2C%202%2C%200.4%29%27%7D%7D%5D%2C%20%27xAxes%27%3A%20%5B%7B%27ticks%27%3A%20%7B%27fontColor%27%3A%20%27%23888888%27%2C%20%27fontSize%27%3A%2011%2C%20%27fontStyle%27%3A%20%27bold%27%7D%2C%20%27gridLines%27%3A%20%7B%27display%27%3A%20false%7D%7D%5D%7D%2C%20%27plugins%27%3A%20%7B%27datalabels%27%3A%20false%7D%7D%7D&format=svg" /></div>

        <h2>📊 Daily Running ({today_date})</h2>
        <ul>
            <li><strong>Name:</strong> No Run Today</li>
            <li><strong>Distance:</strong> 💤 Rest Day</li>
            <li><strong>Pace:</strong> -</li>
            <li><strong>Intensity:</strong> None (Rest Day)</li>
        </ul>
        <blockquote><strong>📋 Coach’s Comment:</strong><br>오늘은 온전한 휴식을 취하며 근육을 재건하고 코어 보강 운동에 집중하는 날입니다. 부상 방지를 위해 휴식도 훈련의 일부입니다.</blockquote>
        <blockquote><strong>🔮 Next Running:</strong><br>🏃‍♂️ Next Target: 5~7km 가벼운 빌드업 조깅 (목표 심박수: 140대)</blockquote>

        <h2>🛠️ Routine For Today</h2>
        <h3>🎯 Objective: Core & Lower Body Reconstruction Routine</h3>
        
        <p style="margin-bottom:5px; font-weight:bold; color:#FC4C02;">🔲 [Step 1] Pre-Run Mobility Warmup</p>
        <ul>
            <li>90/90 Stretching (5 reps L/R, hold 10s)</li>
            <li>Hip Chair Circles (15 reps L/R)</li>
            <li>Toe Yoga / Foot Core (10 reps x 3 sets)</li>
        </ul>

        <p style="margin-bottom:5px; font-weight:bold; color:#FC4C02;">🔲 [Step 2] Post-Run Strength & Recovery Routine</p>
        <ul>
            <li>Deadbug (10 reps x 3 sets)</li>
            <li>Side Plank + Clamshell (12 reps x 3 sets)</li>
            <li>Romanian Deadlift 12kg (12 reps x 3 sets)</li>
            <li>Split Squat 4kg (8 reps L/R x 3 sets)</li>
        </ul>
        
        <footer>Automated via Strava API & QuickChart API</footer>
    </div>
</body>
</html>"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_content)
print("File successfully saved with KST timezone support.")