import json
from pathlib import Path

import joblib
import pandas as pd
import tensorflow as tf


MODEL_DIR = Path(__file__).resolve().parent / "models"

# 학습된 모델과 전처리 정보 불러오기
duration_dnn_model = tf.keras.models.load_model(
    MODEL_DIR / "duration_dnn_model.keras"
)
duration_dnn_scaler = joblib.load(
    MODEL_DIR / "duration_dnn_scaler.pkl"
)
with open(MODEL_DIR / "duration_dnn_features.json", encoding="utf-8") as f:
    duration_dnn_features = json.load(f)


# 예측 함수
def predict_duration(line_id, product_id, target_qty, planned_start_at):

    """작업지시 조건으로 예상 생산 소요시간(시간) 예측"""
		
    # 1. 입력 데이터를 Pandas 데이터프레임으로 변환/저장
    df = pd.DataFrame([{
        "line_id": line_id,
        "product_id": product_id,
        "target_qty": target_qty,
        "planned_start_at": planned_start_at
    }])

    # 2. 날짜 컬럼 변환
    df["planned_start_at"] = pd.to_datetime(df["planned_start_at"])
    
    # 3. 입력 Feature 생성
    df["hour"] = df["planned_start_at"].dt.hour
    df["weekday"] = df["planned_start_at"].dt.weekday
    
    # 4. 범주형 데이터 처리
    df = pd.get_dummies(
        df,
        columns=["line_id", "product_id"]
    )
    # 5. 학습 Feature의 컬럼과 순서 맞추기
    df = df.reindex(columns=duration_dnn_features, fill_value=0)

    # 6. 학습 데이터의 평균·표준편차로 스케일링
    df = duration_dnn_scaler.transform(df)

    # DNN 예측
    pred = duration_dnn_model.predict(df, verbose=0)

    return round(float(pred [0][0]), 2)