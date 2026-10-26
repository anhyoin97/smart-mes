import time
import math
import random
import requests


API_URL = "http://127.0.0.1:8000/api/line-sensor-readings"

LINE_ID = "LINE-01"


for i in range(45):

    # --------------------------------------------
    # 1 ~ 30 : 정상 구간
    # --------------------------------------------
    if i < 30:

        temperature = 61.0 + random.uniform(-0.5, 0.5)
        vibration = 1.2 + random.uniform(-0.1, 0.1)
        current = 10.5 + random.uniform(-0.3, 0.3)
        rpm = 1500 + random.uniform(-15, 15)

        phase = "NORMAL"


    # --------------------------------------------
    # 31 ~ 40 : 경고 구간
    # - 시간이 지날수록 센서값이 점차 변화
    # --------------------------------------------
    elif i < 40:

        step = i - 30

        temperature = (
            61.5
            + step * 0.35
            + random.uniform(-0.3, 0.3)
        )

        vibration = (
            1.3
            + step * 0.08
            + random.uniform(-0.08, 0.08)
        )

        current = (
            10.7
            + step * 0.12
            + random.uniform(-0.2, 0.2)
        )

        rpm = (
            1490
            - step * 4
            + random.uniform(-10, 10)
        )

        phase = "WARNING"


    # --------------------------------------------
    # 41 ~ 45 : 비정상 구간
    # - 큰 변화와 불규칙한 진동 발생
    # --------------------------------------------
    else:

        step = i - 40

        temperature = (
            65.0
            + step * 0.5
            + random.uniform(-0.5, 0.5)
        )

        vibration = (
            2.3
            + abs(math.sin(i)) * 0.8
            + random.uniform(-0.15, 0.15)
        )

        current = (
            12.2
            + step * 0.2
            + random.uniform(-0.3, 0.3)
        )

        rpm = (
            1430
            + math.sin(i * 2) * 70
            + random.uniform(-15, 15)
        )

        phase = "ABNORMAL"


    # MES에 전송할 센서 데이터
    data = {
        "line_id": LINE_ID,
        "temperature": round(temperature, 2),
        "vibration": round(vibration, 2),
        "current": round(current, 2),
        "rpm": round(rpm, 2)
    }


    # API 호출
    response = requests.post(
        API_URL,
        json=data
    )


    print(
        f"{i + 1:02d}분",
        f"[시뮬레이션: {phase}]",
        data
    )

    print(
        "MES 응답:",
        response.json()
    )

    print("-" * 70)


    # 실제 1초 = 시뮬레이션 1분
    time.sleep(1)
