"""생산라인 이상 상태 예측(다중분류) 모델 학습

노션 'ABB_MES수업 / #07. 생산라인 이상 상태 예측' 순서대로 진행한다.

  1-4. 현재 시점의 센서값으로 health_status 분류   -> RandomForest, DNN (단일 시점)
  2.   최근 30분의 센서 흐름으로 '다음 1분'의 상태 분류 -> SimpleRNN, LSTM (30 x 7)

비교한 뒤 RNN 계열 중 검증 성능이 더 좋은 모델을 models/ 폴더로 내보낸다.
(MES 코드는 수정하지 않는다. 내보내기 + 내보낸 파일이 ai_service 방식으로 동작하는지 검증까지만 한다.)

실행: python train_sensor_model.py

시드별 편차 확인용 환경변수 (지정하지 않으면 시드 42, 내보내기 수행):
  SENSOR_SEED=1        무작위 시드 변경 (데이터 분할은 시간순이라 항상 같고, 가중치 초기화/셔플/RF만 달라진다)
  SENSOR_EXPORT=0      models/ 에 파일을 쓰지 않는다 (기존 내보낸 모델을 덮어쓰지 않기 위해)
  SENSOR_RESULT_JSON=경로   모델별 테스트 성능을 JSON 으로 저장
"""
import json
import os
import sqlite3
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import tensorflow as tf
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, recall_score
from sklearn.preprocessing import StandardScaler

# ============================================================
# 설정값 (한 곳에 모아 두고, 아래 단계에서는 이 이름만 사용)
# ============================================================
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "mes.db"
MODEL_DIR = BASE_DIR / "models"

SENSOR_COLS = ["temperature", "vibration", "current", "rpm"]   # 센서 4개
LINES = ["LINE-01", "LINE-02", "LINE-03"]                      # 생산라인 3개
LABELS = ["normal", "warning", "abnormal"]                     # 클래스 이름 (0, 1, 2 순서)
LINE_ONEHOT_COLS = [f"line_id_{line}" for line in LINES]      # 라인 원-핫 컬럼 이름 3개
FEATURES = SENSOR_COLS + LINE_ONEHOT_COLS                      # 모델 입력 Feature 7개 (순서 고정!)

WINDOW = 30         # RNN 입력: 최근 30개(= 30분) 센서값
TRAIN_RATIO = 0.8   # 각 라인의 앞 80% 시간 구간을 학습, 뒤 20%를 테스트로 사용
VAL_RATIO = 0.15    # 학습 구간의 뒤 15%는 검증용(조기종료, 모델 선택)
SEED = int(os.environ.get("SENSOR_SEED", 42))
EXPORT = os.environ.get("SENSOR_EXPORT", "1") == "1"
RESULT_JSON = os.environ.get("SENSOR_RESULT_JSON")

# 파이썬/넘파이/텐서플로 난수를 한 번에 고정한다. 같은 시드면 같은 결과가 재현된다.
tf.keras.utils.set_random_seed(SEED)
print(f"[설정] SEED={SEED}, EXPORT={EXPORT}")

# ============================================================
# 1. 데이터 추출
# ============================================================
# mode=ro : 읽기 전용으로 연다. 학습 스크립트가 실수로 mes.db를 바꾸지 못하게 한다.
with sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True) as conn:
    df = pd.read_sql("SELECT * FROM line_sensor_readings", conn)
print(f"[1] 센서 데이터: {len(df)}행")

# ============================================================
# 2. 시간순 정렬 + 정답(라벨) 숫자 변환
# ============================================================
# measured_at 은 문자열(TEXT)이므로 날짜형으로 바꾼 뒤 라인별·시간순으로 정렬한다.
# RNN은 '순서'가 생명이라 정렬이 틀리면 학습이 의미를 잃는다.
df["measured_at"] = pd.to_datetime(df["measured_at"])
df = df.sort_values(["line_id", "measured_at", "reading_id"]).reset_index(drop=True)

# health_status 가 비어 있는 행은 정답이 없으므로 학습에서 제외한다.
# (나중에 MES가 예측값을 health_status에 저장하면 그 값은 '정답'이 아니라는 점에 주의)
n_before = len(df)
df = df.dropna(subset=["health_status"]).reset_index(drop=True)
if len(df) != n_before:
    print(f"    정답이 없는 {n_before - len(df)}행 제외")

label_to_id = {name: i for i, name in enumerate(LABELS)}
df["y"] = df["health_status"].map(label_to_id)

# ============================================================
# 3. 클래스 분포 확인
# ============================================================
# 불균형(abnormal이 적음)이면 Accuracy만 보면 속기 쉽다 -> 뒤에서 macro-F1, 클래스별 재현율도 본다.
print("\n[3] 클래스 분포")
print(df["health_status"].value_counts().reindex(LABELS).to_string())

# ============================================================
# 4. 학습 / 검증 / 테스트 분할 (시간순, 라인별)
# ============================================================
# 왜 무작위가 아니라 시간순인가?
#   센서는 1분마다 쌓이고 상태는 평균 170분씩 이어진다. 무작위로 나누면 바로 옆 1분짜리 행이
#   학습에도 테스트에도 섞여서(사실상 같은 데이터) 성능이 부풀려진다.
#   그래서 '과거로 학습 -> 미래로 평가'가 되도록 각 라인의 앞쪽 80%를 학습, 뒤쪽 20%를 테스트로 쓴다.
line_data = {}   # 라인별 정보를 모아 두는 딕셔너리
print("\n[4] 라인별 시간순 분할")
for line in LINES:
    g = df[df["line_id"] == line].reset_index(drop=True)
    n = len(g)
    cut = int(n * TRAIN_RATIO)               # 이 위치부터 테스트
    val_start = int(cut * (1 - VAL_RATIO))   # 학습 구간의 뒤쪽 15%는 검증
    line_data[line] = {
        "raw": g[SENSOR_COLS].values.astype(np.float32),  # 스케일링 전 센서값 (n, 4)
        "y": g["y"].values.astype(np.int64),              # 상태 (n,)
        "n": n, "cut": cut, "val_start": val_start,
    }
    print(f"    {line}: 학습 0~{val_start - 1} | 검증 {val_start}~{cut - 1} | 테스트 {cut}~{n - 1}"
          f"  (테스트 시작 {g.loc[cut, 'measured_at']})")

# ============================================================
# 5. 라인별 StandardScaler (노션 2-2)
# ============================================================
# 라인마다 정상 센서 범위가 다르다. 예) 정상 온도 LINE-01 ~61도, LINE-02 ~65도, LINE-03 ~59도.
# 그래서 라인별로 '그 라인의 학습 구간'만으로 평균/표준편차를 구해 따로 스케일링한다.
# (테스트 구간 정보가 평균/표준편차에 새어 들어가지 않도록 반드시 학습 구간만 사용)
#
# 모델 입력 Feature는 7개(센서 4 + 라인 원-핫 3). 노션의 ai_service 코드는 7개 컬럼 전체에
# scaler.transform()을 호출하므로 스케일러도 7개 컬럼으로 만든다.
# 그런데 원-핫 컬럼은 한 라인 안에서는 값이 항상 같아서(0 또는 1) 그냥 두면 표준화 결과가
# 전부 0이 되어 '어느 라인인지' 정보가 사라진다. 그래서 원-핫 컬럼의 평균=0, 표준편차=1로 고정해
# 0/1 값이 그대로 유지되게 만든다.
def onehot_matrix(line, n):
    """라인 하나의 원-핫 행렬(n, 3). 해당 라인 컬럼만 1."""
    m = np.zeros((n, len(LINES)), dtype=np.float32)
    m[:, LINES.index(line)] = 1.0
    return m


scalers = {}
for line in LINES:
    d = line_data[line]
    full = pd.DataFrame(
        np.hstack([d["raw"], onehot_matrix(line, d["n"])]), columns=FEATURES
    )
    # 컬럼 이름을 가진 DataFrame으로 fit 해야, MES에서 DataFrame으로 transform 할 때 경고가 없다.
    scaler = StandardScaler().fit(full.iloc[: d["val_start"]])  # 학습 구간(검증 제외)만 사용
    k = len(SENSOR_COLS)
    scaler.mean_[k:] = 0.0      # 원-핫 컬럼은 평균 0
    scaler.scale_[k:] = 1.0     # 원-핫 컬럼은 표준편차 1  -> (x - 0) / 1 = x
    scaler.var_[k:] = 1.0
    scalers[line] = scaler
    d["z"] = scaler.transform(full).astype(np.float32)   # 스케일링된 (n, 7)
print("\n[5] 라인별 스케일러 생성 완료 (센서 4개만 표준화, 원-핫은 0/1 유지)")

# ============================================================
# 6. 평가 함수
# ============================================================
def report(name, y_true, y_pred):
    """Accuracy, macro-F1, 클래스별 재현율을 한 줄로 출력하고 혼동행렬을 반환."""
    rec = recall_score(y_true, y_pred, labels=[0, 1, 2], average=None, zero_division=0)
    acc = accuracy_score(y_true, y_pred)
    mf1 = f1_score(y_true, y_pred, average="macro")
    print(f"    {name:<14} acc {acc:.3f} | macro-F1 {mf1:.3f} | "
          f"재현율 normal {rec[0]:.3f} warning {rec[1]:.3f} abnormal {rec[2]:.3f}")
    return {"acc": acc, "macro_f1": mf1, "recall": rec.tolist(),
            "cm": confusion_matrix(y_true, y_pred, labels=[0, 1, 2])}


def class_weights(y):
    """클래스가 적을수록 큰 가중치를 줘서 abnormal/warning을 무시하지 않게 한다."""
    counts = np.bincount(y, minlength=3)
    return {i: len(y) / (3 * c) for i, c in enumerate(counts)}


# ============================================================
# 7. [노션 1-4] 단일 시점 모델: RandomForest, DNN
# ============================================================
# 입력: 지금 이 1분의 센서 4개 + 라인 원-핫 3개 (이전 값은 보지 않음)
# 정답: 지금 이 1분의 health_status
# 라인별 스케일러를 쓰는 RNN과 달리 여기서는 라인 구분 없이 전체 학습 구간으로 한 번만 스케일링한다.
def single_point_split(part):
    """part: 'train' | 'val' | 'test' -> (X, y). 라인별 시간 구간을 잘라 모은다."""
    xs, ys = [], []
    for line in LINES:
        d = line_data[line]
        lo, hi = {"train": (0, d["val_start"]),
                  "val": (d["val_start"], d["cut"]),
                  "test": (d["cut"], d["n"])}[part]
        xs.append(np.hstack([d["raw"][lo:hi], onehot_matrix(line, d["n"])[lo:hi]]))
        ys.append(d["y"][lo:hi])
    return np.vstack(xs), np.concatenate(ys)


Xtr, ytr = single_point_split("train")
Xva, yva = single_point_split("val")
Xte, yte = single_point_split("test")
sp_scaler = StandardScaler().fit(Xtr)               # 학습 구간으로만 fit
Xtr_s, Xva_s, Xte_s = (sp_scaler.transform(a) for a in (Xtr, Xva, Xte))

results = {}
print("\n[7] 단일 시점 모델 (테스트 구간)")

# --- RandomForest: 트리 200개, 잎 노드 최소 3개, class_weight 로 불균형 보정
rf = RandomForestClassifier(
    n_estimators=200, min_samples_leaf=3, class_weight="balanced",
    random_state=SEED, n_jobs=-1,
).fit(Xtr_s, ytr)
results["RandomForest(단일)"] = report("RandomForest", yte, rf.predict(Xte_s))

# --- DNN: 입력 7 -> 64 -> 32 -> 3(softmax). softmax는 세 클래스의 확률을 합 1로 출력한다.
dnn = tf.keras.Sequential([
    tf.keras.layers.Input(shape=(len(FEATURES),)),
    tf.keras.layers.Dense(64, activation="relu"),
    tf.keras.layers.Dense(32, activation="relu"),
    tf.keras.layers.Dense(3, activation="softmax"),
])
dnn.compile(optimizer="adam", loss="sparse_categorical_crossentropy")
dnn.fit(
    Xtr_s, ytr, validation_data=(Xva_s, yva), epochs=40, batch_size=128,
    class_weight=class_weights(ytr), verbose=0,
    # 검증 손실이 5번 연속 나아지지 않으면 멈추고, 가장 좋았던 시점의 가중치로 되돌린다.
    callbacks=[tf.keras.callbacks.EarlyStopping(patience=5, restore_best_weights=True)],
)
results["DNN(단일)"] = report("DNN", yte, dnn.predict(Xte_s, verbose=0).argmax(1))

# ============================================================
# 8. [노션 2] 시계열 모델 입력 만들기: 30 x 7 윈도우
# ============================================================
# 윈도우 i : i-30 ~ i-1 번째 센서값(과거 30분)  ->  정답 : i 번째 health_status(다음 1분)
#   1~30번째 센서값 -> 31번째 상태, 2~31번째 -> 32번째 상태 ... 한 칸씩 밀면서 만든다.
# 윈도우는 반드시 '한 라인 안에서만' 만든다. 라인이 바뀌는 경계를 걸치면 서로 다른 설비 데이터가 섞인다.
def make_windows(part):
    """part: 'train' | 'val' | 'test' -> X (샘플, 30, 7), y (샘플,)

    정답이 속한 시점 i 가 해당 구간(part)에 있으면 그 윈도우는 그 구간 소속이다.
    테스트 윈도우의 입력(과거 30분)이 학습 구간 끝과 겹쳐도 괜찮다.
    '과거 센서값'만 입력으로 쓰고, 정답은 모두 테스트 구간의 값이기 때문이다.
    """
    xs, ys = [], []
    for line in LINES:
        d = line_data[line]
        lo, hi = {"train": (WINDOW, d["val_start"]),
                  "val": (d["val_start"], d["cut"]),
                  "test": (d["cut"], d["n"])}[part]
        for i in range(lo, hi):
            xs.append(d["z"][i - WINDOW: i])
            ys.append(d["y"][i])
    return np.array(xs, dtype=np.float32), np.array(ys, dtype=np.int64)


Xtr_w, ytr_w = make_windows("train")
Xva_w, yva_w = make_windows("val")
Xte_w, yte_w = make_windows("test")
print(f"\n[8] 윈도우 생성: 학습 {Xtr_w.shape}, 검증 {Xva_w.shape}, 테스트 {Xte_w.shape}")
print(f"    테스트 클래스 분포 {np.bincount(yte_w, minlength=3).tolist()}")

# ============================================================
# 9. RNN 계열 모델 학습: SimpleRNN, LSTM
# ============================================================
# SimpleRNN : 가장 기본적인 순환 신경망. 구조가 단순하지만 긴 흐름은 잘 기억하지 못한다.
# LSTM      : 기억을 '게이트'로 조절해서 더 긴 흐름을 다룰 수 있다.
# 둘 다 입력 (30, 7) -> 순환층(32) -> Dense(32) -> Dense(3, softmax).
def build_and_train(recurrent_layer):
    model = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(WINDOW, len(FEATURES))),
        recurrent_layer,
        tf.keras.layers.Dense(32, activation="relu"),
        tf.keras.layers.Dense(3, activation="softmax"),
    ])
    model.compile(optimizer="adam", loss="sparse_categorical_crossentropy")
    model.fit(
        Xtr_w, ytr_w, validation_data=(Xva_w, yva_w), epochs=40, batch_size=128,
        class_weight=class_weights(ytr_w), verbose=0,
        callbacks=[tf.keras.callbacks.EarlyStopping(patience=5, restore_best_weights=True)],
    )
    return model


print("\n[9] 시계열 모델 학습 중 (30분 윈도우, 다음 1분 상태 예측)")
rnn_models = {
    "SimpleRNN": build_and_train(tf.keras.layers.SimpleRNN(32)),
    "LSTM": build_and_train(tf.keras.layers.LSTM(32)),
}

# 모델 선택은 '검증 구간'의 macro-F1로 한다. 테스트로 고르면 테스트가 선택에 쓰여 평가가 낙관적이 된다.
print("    검증 구간 성능 (모델 선택용)")
val_f1 = {}
for name, m in rnn_models.items():
    val_f1[name] = report(name, yva_w, m.predict(Xva_w, verbose=0).argmax(1))["macro_f1"]
best_name = max(val_f1, key=val_f1.get)
best_model = rnn_models[best_name]
print(f"    -> 검증 macro-F1 기준 선택: {best_name}")

print("\n    테스트 구간 성능 (최종 평가)")
test_proba = {}
for name, m in rnn_models.items():
    test_proba[name] = m.predict(Xte_w, verbose=0)
    results[f"{name}(30분)"] = report(name, yte_w, test_proba[name].argmax(1))

# ============================================================
# 10. 최종 비교표
# ============================================================
print("\n[10] 최종 비교 (테스트 구간)")
print(f"    {'모델':<20}{'Accuracy':>9}{'macro-F1':>10}{'normal':>8}{'warning':>9}{'abnormal':>9}")
for name, r in results.items():
    rc = r["recall"]
    print(f"    {name:<20}{r['acc']:>9.3f}{r['macro_f1']:>10.3f}{rc[0]:>8.3f}{rc[1]:>9.3f}{rc[2]:>9.3f}")
print(f"\n    선택한 모델({best_name}) 혼동행렬 (행=실제, 열=예측, 순서 normal/warning/abnormal)")
print(results[f"{best_name}(30분)"]["cm"])

# 시드별 편차 비교를 위해 결과를 JSON 으로 저장 (선택한 RNN 이름과 검증 점수 포함)
if RESULT_JSON:
    dump = {"seed": SEED, "selected_by_val": best_name, "val_macro_f1": val_f1,
            "test": {k: {"acc": v["acc"], "macro_f1": v["macro_f1"], "recall": v["recall"],
                         "cm": v["cm"].tolist()} for k, v in results.items()}}
    Path(RESULT_JSON).write_text(json.dumps(dump, ensure_ascii=False, indent=2), encoding="utf-8")

# ============================================================
# 11. 모델 내보내기 (노션 2-3 파일 구성 그대로)
# ============================================================
# models/
#   sensor_rnn_model.keras          학습된 시계열 모델
#   line1_sensor_rnn_scaler.pkl     LINE-01 전용 스케일러
#   line2_sensor_rnn_scaler.pkl     LINE-02 전용 스케일러
#   line3_sensor_rnn_scaler.pkl     LINE-03 전용 스케일러
#   sensor_rnn_features.json        입력 컬럼 7개와 순서 (서비스에서 컬럼 순서를 맞출 때 사용)
if not EXPORT:
    # 시드 비교 실험일 때는 여기서 끝낸다. (기존에 내보낸 모델을 덮어쓰지 않는다.)
    print("\n[11] SENSOR_EXPORT=0 이므로 내보내기/검증을 건너뜁니다.")
    raise SystemExit(0)

MODEL_DIR.mkdir(exist_ok=True)
best_model.save(MODEL_DIR / "sensor_rnn_model.keras")
for i, line in enumerate(LINES, start=1):
    joblib.dump(scalers[line], MODEL_DIR / f"line{i}_sensor_rnn_scaler.pkl")
with open(MODEL_DIR / "sensor_rnn_features.json", "w", encoding="utf-8") as f:
    json.dump(FEATURES, f, ensure_ascii=False, indent=4)
print(f"\n[11] 내보내기 완료 -> {MODEL_DIR}")

# ============================================================
# 12. 내보낸 파일 검증 (MES에서 쓰는 방식 그대로 예측해 보기)
# ============================================================
# 학습 코드와 서비스 코드는 입력을 만드는 방식이 달라서, 여기서 어긋나면 서비스에서 엉뚱한 값이 나온다.
# 그래서 노션 2-4의 predict_sensor_status 와 같은 단계(DataFrame -> 원-핫 -> 컬럼 정렬
# -> 라인별 스케일러 -> reshape(1, 30, 7) -> predict)를 '저장된 파일'로 직접 수행하고,
# 학습 중 메모리에 있던 모델의 결과와 같은지 비교한다.
loaded_model = tf.keras.models.load_model(MODEL_DIR / "sensor_rnn_model.keras")
loaded_scalers = {line: joblib.load(MODEL_DIR / f"line{i}_sensor_rnn_scaler.pkl")
                  for i, line in enumerate(LINES, start=1)}
loaded_features = json.load(open(MODEL_DIR / "sensor_rnn_features.json", encoding="utf-8"))


def predict_like_service(line_id, sensor_rows):
    """노션의 predict_sensor_status 와 같은 전처리를 저장된 파일로 수행 (확률 3개 반환)."""
    x = pd.DataFrame(sensor_rows, columns=SENSOR_COLS)
    x["line_id"] = line_id
    x = pd.get_dummies(x, columns=["line_id"])
    x = x.reindex(columns=loaded_features, fill_value=0)
    x = x.astype(float)                       # get_dummies 가 bool 로 만들 수 있어 숫자로 통일
    x = loaded_scalers[line_id].transform(x)
    return loaded_model.predict(x.reshape(1, WINDOW, len(FEATURES)), verbose=0)[0]


rng = np.random.default_rng(SEED)
checked, max_diff, mismatch = 0, 0.0, 0
for line in LINES:
    d = line_data[line]
    for i in rng.choice(np.arange(d["cut"], d["n"]), size=40, replace=False):
        proba_service = predict_like_service(line, d["raw"][i - WINDOW: i])
        # 같은 윈도우를 학습 코드 경로(이미 스케일링된 z)로 예측한 값
        proba_train = best_model.predict(d["z"][i - WINDOW: i][None], verbose=0)[0]
        max_diff = max(max_diff, float(np.abs(proba_service - proba_train).max()))
        mismatch += int(proba_service.argmax() != proba_train.argmax())
        checked += 1
print(f"\n[12] 저장 파일 검증: {checked}개 윈도우, 예측 클래스 불일치 {mismatch}개, 확률 최대 차이 {max_diff:.2e}")
print("     (불일치 0, 차이가 1e-6 수준이면 서비스에서도 학습 때와 같은 결과가 나온다)")
