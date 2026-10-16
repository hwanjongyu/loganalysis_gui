# Post Phase 3: High-Performance Concurrency & Virtualization Plan (Phase 4)

## 1. 개요 (Overview)

Phase 1(안정성/크래시 방지), Phase 2(보안/동시성 강화), Phase 3(아키텍처 모듈화/도메인 분리)의 성공적인 완료를 바탕으로, 본 계획은 **대용량 로그(수백만 라인) 환경에서의 초저지연 UI 반응성(Zero-Jank UI)** 및 **완전한 컴포넌트 격리**를 달성하기 위한 **Post Phase 3 (Phase 4)** 고도화 로드맵을 정의합니다.

---

## 2. 핵심 목표 (Core Objectives)

1. **Non-blocking Off-Thread Search (`SearchWorker`)**: 수백만 라인 로그 검색 시 GUI 메인 스레드 프리징을 완전히 제거하고 즉각적인 취소(Cancellation) 및 진행률(Progress) 지원.
2. **Style Precomputation Pipeline (Offload-Then-Redo Anti-pattern 제거)**: `FilterWorker` 필터링 과정에서 스타일/색상 매핑을 사전 계산하여 뷰포트 스크롤링 시 메인 스레드 정규식 재평가 오버헤드 0% 달성.
3. **Non-blocking ADB Device Polling (`AdbDeviceScanWorker`)**: 디바이스 목록 스캔(`adb devices`) 시 adb 서버 지연으로 인한 메인 스레드 3초 블로킹 제거.
4. **`LogViewController` 분리**: 메인 윈도우에 남아 있는 뷰포트 컬럼 너비 계산, 전체 라인 표시 모드, 커스텀 컨텍스트 메뉴 로직을 전용 컨트롤러로 이관하여 `main_window.py`를 순수 오케스트레이터로 경량화 (< 800 lines).

---

## 3. 세부 작업 명세 (Detailed Tasks)

```mermaid
graph TD
    subgraph UI Layer (Main Thread)
        MW["LogAnalysisMainWindow"]
        LVC["LogViewController (NEW)"]
        SC["SearchController"]
        AC["AdbController"]
        FM["FilterManager"]
    end

    subgraph Data Models & Storage
        LM["LogModel"]
        SM["Precomputed Style Array (NEW)"]
    end

    subgraph Asynchronous QThreads (Off-Thread)
        SW["SearchWorker (D1: Non-blocking Find)"]
        FW["FilterWorker (D2: Visibility + Style Precompute)"]
        ADW["AdbDeviceScanWorker (D3: Async Devices Scan)"]
    end

    MW --> LVC
    MW --> SC
    MW --> AC
    MW --> FM

    SC -.->|Trigger / Cancel| SW
    SW -.->|match_found(row, len)| SC

    FM -.->|Trigger| FW
    FW -.->|visible_indices + styles| LM
    LM --> SM

    AC -.->|Trigger| ADW
    ADW -.->|devices_loaded(list)| AC
```

---

### D1. 비동기 검색 워커 (`SearchWorker`) 도입
- **현상 및 문제점**:
  - [`src/loganalysis_gui/search_controller.py`](file:///home/drew/github/hwanjongyu/loganalysis_gui/src/loganalysis_gui/search_controller.py)의 `find_in_files()`가 GUI 메인 스레드에서 수백만 라인을 동기 반복문으로 검색.
  - 정규식이 복잡하거나 매칭되지 않는 경우 검색이 끝날 때까지 GUI가 멈춤(Not Responding).
- **개선 방안**:
  - [`src/loganalysis_gui/workers.py`](file:///home/drew/github/hwanjongyu/loganalysis_gui/src/loganalysis_gui/workers.py)에 `SearchWorker(QThread)` 구현.
    - 입력: `lines_snapshot`, `pattern`, `start_row`, `is_forward`, `is_regex`, `match_case`
    - 시그널: `match_found(int, int)`, `search_finished(bool)`, `progress(int)`
    - 취소 메커니즘: `is_cancelled` 플래그 및 검색 요청 번호(`req_id`) 검증.
  - `SearchController`가 이전 검색 작업을 즉시 중단하고 신규 검색을 비동기로 시작.

---

### D2. 필터-스타일 사전 계산 파이프라인 통합 (Offload-Then-Redo 제거)
- **현상 및 문제점**:
  - `FilterWorker`가 백그라운드에서 `find_matching_filters()`를 돌려 라인의 매칭 여부를 확인하고 `visible_indices`만 반환함.
  - 사용자가 로그 뷰를 스크롤할 때 `LogModel.data()`가 다시 `find_matching_filters()`를 호출하여 글자색/배경색을 계산함.
  - LRU 스타일 캐시(10k)가 존재하지만 빠른 스크롤 시 캐시 미스 발생 시 메인 스레드에서 정규식 평가 연산이 중복 실행됨.
- **개선 방안**:
  - `FilterWorker`가 라인을 판별할 때 매칭된 최상위 필터의 스타일 ID(또는 색상 튜플)를 함께 수집하여 `List[Tuple[int, int]]` (row, style_id) 또는 밀집 인덱스 배열로 방출.
  - `LogModel`은 필터링 완료 시 스타일 매핑 테이블을 직접 수신하여 `data()` 호출 시 정규식 연산 없이 $O(1)$ 직접 인덱싱으로 스타일 반환.

---

### D3. 비동기 ADB 디바이스 스캔 (`AdbDeviceScanWorker`)
- **현상 및 문제점**:
  - [`src/loganalysis_gui/adb_controller.py`](file:///home/drew/github/hwanjongyu/loganalysis_gui/src/loganalysis_gui/adb_controller.py)의 `refresh_devices()`가 `subprocess.check_output([adb_path, "devices"], timeout=3.0)`을 메인 스레드에서 실행.
  - ADB 데몬이 재시작 중이거나 USB 장치가 응답하지 않을 때 최대 3초 동안 GUI 인터랙션 차단.
- **개선 방안**:
  - `AdbDeviceScanWorker(QThread)` 또는 `QThreadPool` 기반 단발성 워커로 분리.
  - 스캔 중에는 새로고침 아이콘 비활성화 및 스피너/상태 표시, 완료 시 시그널로 디바이스 목록 업데이트.

---

### D4. `LogViewController` 분리 (뷰/프레젠테이션 계층 완전 분리)
- **현상 및 문제점**:
  - `LogAnalysisMainWindow`에 여전히 컬럼 너비 조정(`_adjust_column_width`), 전체 라인 표시 토글(`set_full_line_display_enabled`), 폰트 메트릭 계산, 로그 뷰 컨텍스트 메뉴 표시 등의 로직이 남아 있음 (~300 라인).
- **개선 방안**:
  - [`src/loganalysis_gui/log_view_controller.py`](file:///home/drew/github/hwanjongyu/loganalysis_gui/src/loganalysis_gui/log_view_controller.py)를 신설.
  - `LogView` 위젯의 프레젠테이션 로직(컬럼 너비, 뷰 모드 인디케이터, 복사/컨텍스트 메뉴)을 캡슐화.
  - `MainWindow`의 코드 라인 수를 800줄 이하로 대폭 축소하여 가독성과 유지보수성 극대화.

---

## 4. 단계별 실행 계획 (Milestones)

| 단계 | 항목 | 주요 변경 파일 | 진행 상태 |
| :---: | :--- | :--- | :---: |
| **Step 1** | **D1: 비동기 SearchWorker** | `workers.py`, `search_controller.py`, `constants.py` | **완료 (테스트 통과)** |
| **Step 2** | **D3: 비동기 ADB 디바이스 스캔** | `workers.py`, `adb_controller.py` | **완료 (테스트 통과)** |
| **Step 3** | **D2: 필터-스타일 파이프라인 통합** | `workers.py`, `models.py`, `filter_engine.py` | **완료 (테스트 77/77 Pass)** |
| **Step 4** | **D4: LogViewController 분리** | `log_view_controller.py`, `main_window.py` | 대기 |

---

## 5. 검증 계획 (Verification Strategy)

1. **단위 테스트 스위트 확장**:
   - `test_search_worker_cancellation_and_progress`: 검색 중 취소 시그널 및 정상 매칭 검증.
   - `test_adb_device_scan_async`: 비동기 디바이스 응답 및 타임아웃 처리 검증.
   - `test_precomputed_style_pipeline`: 필터링 완료 후 `LogModel.data()`가 사전 계산된 스타일을 즉시 반환하는지 검증.
2. **기존 65개 단위 테스트 무결성 유지**:
   - 기존의 모든 mock patch 및 API 계약 유지 (0 Failures, 0 Errors).
3. **벤치마크**:
   - 200만 라인 로그 기준 검색 시 UI 응답성(FPS) 및 스크롤 시 프레임 드랍(Jank) 측정.
