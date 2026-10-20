"""납기 준수 여부 예측(분류) 모델 학습 - RandomForest vs DNN 비교 후 내보내기

노션 'ABB_MES수업 / 납기 준수 여부 예측 모델' 순서대로 진행
실행: python train_late_model.py
"""
import json
import sqlite3
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import tensorflow as tf
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "models"

# ------------------------------------------------------------
# 1. 학습 데이터 준비 (완료된 작업지시만)
# ------------------------------------------------------------
with sqlite3.connect(BASE_DIR / "mes.db") as conn:
    df = pd.read_sql(
        """
        SELECT work_order_id, line_id, product_id, target_qty,
               planned_start_at, due_at, actual_start_at, actual_end_at
        FROM work_orders
        WHERE status = 'completed'
        """,
        conn,
    )
print("[1] 완료 작업지시:", len(df))

# ------------------------------------------------------------
# 2. 날짜 변환
# ------------------------------------------------------------
print("\n[2] 변환 전")
df.info()
for col in ["planned_start_at", "due_at", "actual_start_at", "actual_end_at"]:
    df[col] = pd.to_datetime(df[col])
print("\n[2] 변환 후 dtypes")
print(df.dtypes)

# ------------------------------------------------------------
# 3. 정답 생성 (late: 0 정상 / 1 지연)
# ------------------------------------------------------------
df["late"] = (df["actual_end_at"] > df["due_at"]).astype(int)

# ------------------------------------------------------------
# 4. Feature 생성 (등록 시점에 알 수 있는 정보만)
# ------------------------------------------------------------
df["hour"] = df["planned_start_at"].dt.hour
df["weekday"] = df["planned_start_at"].dt.weekday
df["slack_h"] = (df["due_at"] - df["planned_start_at"]).dt.total_seconds() / 3600

# ------------------------------------------------------------
# 5. 납기 지연 분포 확인
# ------------------------------------------------------------
print("\n[5] late 분포")
print(df["late"].value_counts().sort_index())
print(df["late"].value_counts(normalize=True).sort_index().round(3))

# ------------------------------------------------------------
# 6~7. 범주형 One-Hot + 학습 Feature 정의 (13개)
# ------------------------------------------------------------
df = pd.get_dummies(df, columns=["line_id", "product_id"])

features = [
    "target_qty", "hour", "weekday", "slack_h",
    "line_id_LINE-01", "line_id_LINE-02", "line_id_LINE-03",
    "product_id_PROD-A", "product_id_PROD-B", "product_id_PROD-C",
    "product_id_PROD-D", "product_id_PROD-E", "product_id_PROD-F",
]
X = df[features].astype(float)
y = df["late"]
print("\n[7] Feature 수:", len(features))

# ------------------------------------------------------------
# 8. 학습/테스트 분리 (8:2, 클래스 비율 유지)
# ------------------------------------------------------------
train_x, test_x, train_y, test_y = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)
print("[8]", train_x.shape, test_x.shape, train_y.shape, test_y.shape)
print("    train late 비율:", round(train_y.mean(), 3), "/ test late 비율:", round(test_y.mean(), 3))

# ------------------------------------------------------------
# 9. Scaling (train에만 fit)
# ------------------------------------------------------------
scaler = StandardScaler()
train_x_s = scaler.fit_transform(train_x)
test_x_s = scaler.transform(test_x)


def evaluate(name, y_true, y_pred):
    cm = confusion_matrix(y_true, y_pred)
    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "precision": precision_score(y_true, y_pred),
        "recall": recall_score(y_true, y_pred),
        "f1": f1_score(y_true, y_pred),
        "missed_late": int(cm[1][0]),  # 실제 지연 + 예측 정상
    }


# ------------------------------------------------------------
# 10. RandomForest 분류 모델
# ------------------------------------------------------------
rf = RandomForestClassifier(n_estimators=130, min_samples_leaf=3, random_state=42)
rf.fit(train_x_s, train_y)
rf_pred = rf.predict(test_x_s)
rf_result = evaluate("RandomForest", test_y, rf_pred)

# ------------------------------------------------------------
# 11. TensorFlow DNN 이진분류 모델
# ------------------------------------------------------------
tf.keras.utils.set_random_seed(42)
dnn = tf.keras.Sequential([
    tf.keras.layers.Input(shape=(train_x_s.shape[1],)),
    tf.keras.layers.Dense(64, activation="relu"),
    tf.keras.layers.Dense(32, activation="relu"),
    tf.keras.layers.Dense(1, activation="sigmoid"),
])
dnn.compile(optimizer="adam", loss="binary_crossentropy", metrics=["accuracy"])
dnn.fit(
    train_x_s, train_y.values,
    validation_split=0.2,
    epochs=200,
    batch_size=32,
    callbacks=[tf.keras.callbacks.EarlyStopping(
        monitor="val_loss", patience=15, restore_best_weights=True
    )],
    verbose=0,
)
dnn_prob = dnn.predict(test_x_s, verbose=0).ravel()
dnn_pred = (dnn_prob >= 0.5).astype(int)  # 확률 >= 0.5 → 지연
dnn_result = evaluate("DNN", test_y, dnn_pred)

# ------------------------------------------------------------
# 12. 비교
# ------------------------------------------------------------
comparison = pd.DataFrame({"RandomForest": rf_result, "DNN": dnn_result}).T.round(4)
print("\n===== 성능 비교 =====")
print(comparison)

# ------------------------------------------------------------
# 13. 모델 내보내기 (현재 서비스 중인 소요시간 모델 파일은 건드리지 않음)
# ------------------------------------------------------------
MODEL_DIR.mkdir(exist_ok=True)
dnn.save(MODEL_DIR / "late_dnn_model.keras")
joblib.dump(rf, MODEL_DIR / "late_rf_model.pkl")
joblib.dump(scaler, MODEL_DIR / "late_scaler.pkl")
with open(MODEL_DIR / "late_features.json", "w", encoding="utf-8") as f:
    json.dump(features, f, ensure_ascii=False, indent=4)
print("\n[13] 내보내기 완료:", [p.name for p in MODEL_DIR.glob("late_*")])
