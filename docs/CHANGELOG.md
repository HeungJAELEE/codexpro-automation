# 기술 변경 기록

README는 현재 제품의 목적과 사용법만 설명합니다. 구현 변경, 호환 패치,
레거시 이전 기록은 이 문서에서 관리합니다.

## 현재 릴리스

### GitHub + Codex Cloud 기본 실행 경로

- GitHub commit/branch를 저장소 정본으로 사용하고 Codex Cloud를 신규
  repository 작업의 기본 실행 경로로 승격했습니다.
- Oracle·DevSpace·CodexPro Bridge·Tailscale은 로컬 미공개 파일, 로그인된
  데스크톱 앱, persisted run 복구를 위한 명시적 로컬 경로로 격리했습니다.
- dirty working tree는 명시적 backup branch로 안전하게 동기화하거나
  차단하며, cloud가 누락 바이트를 추정하지 않습니다.
- Linux CI에서 cloud routing contract와 PC 비의존성을 검사하고, 실제 완료는
  원격 branch/PR 및 exact commit CI로만 판정합니다.

### Oracle 지휘 라우트와 제출 전 복구

- Oracle 하위 실행기의 `mode=browser`와 dispatcher의 의미 계약
  `dispatch_mode=orchestrator`를 내구 상태에 함께 기록합니다.
- Luna supervisor는 `browser + orchestrator + devspace` 조합을 검증하며,
  존재할 수 없는 `mode=orchestrator` 상태를 요구하지 않습니다.
- `ChatGPT browser manual-login profile is not initialized` 오류를 composer
  이전 호스트 실패로 분류합니다. 대화 URL과 다른 실행 소유권이 없을 때만
  `safe_for_fresh_run`을 허용합니다.
- `pre-submit-failed` 전이는 실패한 예약과 incident 근거를 삭제하지 않고
  `PRE_SUBMIT_FAILED`로 보존한 뒤 남은 승인 횟수 안에서 새 미리보기와 예약을
  만들게 합니다. 동일 실행 자동 재시도는 하지 않습니다.

### Luna 시작 게이트 보정

- 현재 Codex task에 성공적으로 적용된 `gpt-5.6-luna/high` 모델 지정
  영수증을 런타임 증거로 인정하고, Web GPT의 `Extra High`와 Luna reasoning
  effort를 분리해 보고합니다.
- 원본 checkout이 dirty이면 stash·reset·임의 commit하지 않고,
  `startingState: working-tree`인 별도 Codex worktree task로 현재 상태를
  보존·격리한 뒤 clean boundary에서만 supervisor를 준비합니다.
- 사용자가 Notion 주소 자동 채움을 요청하면 같은 Project에 연결되고 AI
  접근이 허용된 유일한 기존 Task·Report를 canonical readback으로 확정합니다.
- 과거 task의 Oracle patch 누락 보고보다 현재 설치 artifact의 존재·hash
  readback을 우선해 복구 후에도 오래된 실패로 다시 막히지 않게 합니다.

### Luna 연속 지휘모드

- 기존 `$web-gpt`를 변경하지 않고 명시 호출형 `$luna-web-supervisor`를
  추가했습니다.
- Luna는 제품 소스를 고치지 않고 직렬 Web GPT 제출·정확한 slug 복구·Git
  경계 검증·선언된 테스트·Notion 기록과 readback만 담당합니다.
- 검증 실패는 즉시 종료하지 않습니다. 실패 증거와 허용 파일을 고정한 개선
  미션을 만든 뒤 Notion에 시도 내역을 기록하고, 남은 승인 횟수 안에서 새 Web
  GPT 실행에 판단·수정·테스트·local commit을 다시 맡깁니다.
- 단위별 `max_web_attempts`, 전체 제출 상한, 정확한 outcome별 net diff,
  기록 완료 전 다음 단위 차단으로 무한 반복과 권한 확대를 막습니다.

### Oracle 호환 패치 설치 무결성

- Windows 전역 설치 manifest가 Oracle 호환 계층에 선언된 모든 패치 파일을
  포함하는지 동적으로 검사합니다.
- 필수 패치가 없으면 Oracle나 브라우저를 시작하기 전에
  `ORACLE_COMPAT_PATCH_MISSING`으로 중단하고 설치 artifact 누락을 명확히
  보고합니다.
- 과거의 동일한 `FileNotFoundError` 실행도 제출 전 호스트 환경 실패로
  재판정하므로 새 실행 안전성 판단이 모호한 `unclassified`에 머물지 않습니다.

### Oracle + DevSpace 단일 실행 경로

- 일반 GPT, 계획, 검토, 수정, 지휘, 심층 리서치, 종합모드와 Web
  Multi-GPT를 Oracle + DevSpace로 통일했습니다.
- Pro는 Oracle 첨부 전용이며 DevSpace를 사용하지 않습니다.
- CodexPro와 agbrowse 신규 제출 경로는 동결했습니다.

### Windows 브라우저 실행 격리

- 실행마다 로그인 프로필의 throwaway 복사본을 사용합니다.
- Windows에서는 Node 내장 복사로 프로필을 만들며 rsync를 요구하지 않습니다.
- 각 Oracle 실행이 소유한 숨김 Chrome만 정리합니다.

### 장기 작업과 복구

- 비Pro 작업은 기본 `--browser-timeout 90m`을 사용합니다.
- Oracle의 재로드·fallback은 같은 90분 예산의 남은 시간만 사용합니다.
- CDP 호출이 멈춰도 host watchdog이 30초 grace 뒤 동일 세션을 보존한 채
  `attention_required`로 반환합니다.
- 제출 후 로컬 종료·브라우저 연결 끊김은 `attention_required`로 보존합니다.
- 복구는 저장된 정확한 slug와 대화 URL만 사용하고 새 질문을 보내지 않습니다.
- terminal 상태는 이후 관찰에서 live로 되돌아가지 않습니다.

### 종합모드

- plan → optional Pro/Web Multi → review → implementation → final web gate
  → local deterministic gate 순서를 사용합니다.
- 각 단계는 다음 미션과 workflow/stage/attempt/input-SHA 결합 영수증을
  직접 작성합니다.
- review 단계가 수정 가능한 계획 결함을 직접 고치고 구현 미션을 확정합니다.
- Pro 증거 파일은 `[PRO_ATTACHMENT_CONTRACT]`에 선언된 파일만 첨부합니다.
- 손상된 Pro JSON은 신원이 정확히 일치하는 제한된 경우에만 감사 기록과
  함께 복구합니다.

### Web Multi-GPT

- 독립 Oracle solver 2~25개를 최대 5개씩 wave로 실행합니다.
- Windows lane마다 별도 프로필을 사용합니다.
- 각 solver는 짧은 handoff 파일을 만들고 merger 하나가 안정된 순서로
  결과를 병합합니다.

### 설치와 릴리스

- 설치 전 파일을 백업하고 durable 영수증을 남깁니다.
- 기본 설치는 동결된 agbrowse/CodexPro 의존성을 설치하거나 갱신하지 않습니다.
- portability, fast gate, golden-path, v3/v4 계약 테스트를 CI에서 실행합니다.

## 레거시 기록

과거 CodexPro·agbrowse 기반 v1~v4 실행기와 goal supervisor는 새 작업을
만들 수 없습니다. 이미 저장된 실행을 원래 신원으로 복구할 때만 사용합니다.
자세한 목록은 [FROZEN_LEGACY.md](FROZEN_LEGACY.md)에 있습니다.

세부 커밋 단위 변경은 Git 로그와 GitHub Releases/Actions를 권위 기록으로
사용합니다.
