# Codex Web GPT Orchestrator

한국어 | [English](README.en.md)

GitHub를 정본으로 삼아 Codex Cloud가 계획·구현·테스트·PR을 수행하는
cloud-first 운영 도구입니다. 기본 실행 경로는 Codex Cloud이며 PC가 꺼져 있어도
저장소 작업을 계속할 수 있습니다.

기존 Windows Oracle·DevSpace 자동화는 삭제하지 않습니다. 원격에 없는 로컬
파일, 로그인된 데스크톱 앱, 과거 실행의 정확한 복구가 필요할 때만 사용하는
명시적 로컬 보조 경로입니다.

선택적 로컬 경로는 다음 두 도구를 연결합니다.

- [Oracle](https://github.com/steipete/oracle): 로그인된 ChatGPT 브라우저
  세션 생성, 모델 선택, 응답 대기와 결과 회수
- [DevSpace](https://github.com/Waishnav/devspace): 사용자가 허용한 로컬
  프로젝트의 파일 읽기·쓰기와 명령 실행

일반 cloud 작업은 GitHub branch/commit에서 시작해 검토 가능한 diff와 PR을
남깁니다. 로컬 GPT 작업을 명시적으로 선택한 경우에만 Oracle이 `@DevSpace`와
미션 파일 경로를 ChatGPT에 전달합니다.

## 이 도구로 할 수 있는 일

- PC 없이 GitHub 저장소를 checkout하고 수정·테스트·PR·CI 검증
- 로컬 dirty working tree를 명시적 백업 브랜치로 이관하거나 안전하게 차단
- 웹 GPT가 로컬 프로젝트를 읽고 직접 수정·테스트
- Luna가 웹 GPT의 연속 구현을 감시·검증·기록하고 실패를 다시 웹에 보내 개선
- 계획, 검토, 수정, 지휘, 심층 리서치 모드
- 여러 독립 ChatGPT 세션을 동시에 실행하는 Web Multi-GPT
- PC 로컬 Codex 레인을 병렬 실행하는 읽기 전용 Local Multi-GPT
- 계획 → 검토 → 구현 → 최종 검증을 연결하는 종합모드
- 프로젝트별 실행 잠금, 미션·첨부 해시, 정확한 세션 복구
- 다른 프로젝트의 ChatGPT 작업과 분리된 브라우저 프로필
- 작업 완료 후 Oracle 소유 대화 자동 보관
- 설치 파일 백업, 설치 영수증, 롤백

## 동작 구조

```text
사용자 요청
    ↓
GitHub의 정확한 branch/commit 선택
    ↓
Codex Cloud 환경이 저장소 checkout + AGENTS.md 로드
    ↓
Cloud에서 탐색·수정·테스트·diff 검토
    ↓
전용 branch push + Pull Request
    ↓
정확한 commit의 CI 확인
```

로컬 전용 파일이나 데스크톱 세션이 필요한 작업만 Oracle + DevSpace 경로로
분기합니다. 이 경로의 호스트 상태와 ChatGPT 출력은 DevSpace 프로젝트 밖의
`%USERPROFILE%\.codex\state\chatgpt-oracle`에 저장됩니다.

## 모드

| 모드 | CLI/영어 이름 | 용도 | 실행 방식 |
|---|---|---|---|
| Cloud 기본 | Codex Cloud / Cloud Work | 저장소 기반 계획·구현·테스트·PR | GitHub + 격리 cloud 환경 |
| 일반 GPT | `direct` / GPT | 질문·분석·작은 작업 | Oracle + DevSpace, 단일 세션 |
| 계획 | `plan` / plan | 구현 전 설계 | Oracle + DevSpace, 읽기 전용 |
| 검토 | `review` / review | 코드·계획의 독립 검토 | Oracle + DevSpace, 읽기 전용 |
| 수정 | `edit` / edit | 정해진 범위의 수정·테스트 | Oracle + DevSpace |
| 지휘 | `orchestrator` / orchestrator | 계획이 확정된 작업을 한 GPT가 끝까지 수행 | Oracle + DevSpace, 단일 세션 |
| 심층 리서치 | `deep-research` / deep research | 공개 자료와 프로젝트 증거 조사 | Oracle Deep Research + DevSpace |
| Web Multi-GPT | Web Multi-GPT | 여러 관점의 독립 탐색·검증 | 독립 Oracle 세션 2~25개 + merger |
| Local Multi-GPT | Local Multi-GPT | 로컬 병렬 자문·반례 탐색 | `gpt-5.6-luna` + `max` 고정, 읽기 전용 |
| Luna 연속 지휘 | `$luna-web-supervisor` / 연속 지휘모드 | 웹 GPT 구현을 직렬 감시·검증·기록하고 실패를 웹에 재전달 | Luna `high` 감독 + Oracle DevSpace Sol Extra High |
| 종합모드 | comprehensive mode | 계획부터 구현·최종 게이트까지 자동 연결 | plan → optional Pro/Multi → review → implementation → gate |
| Pro | `pro` / Pro | 독립적인 최종 판단·설계 검토 후 결과만 반환 | Oracle 첨부 전용, DevSpace 없음 |

지휘는 웹 제출 한 번으로 끝나는 실행 모드입니다. 종합모드는 지휘와 같은
구현 단계를 포함하면서 계획·독립 검토·선택적 Pro/Web Multi·최종 게이트를
추가한 다단계 워크플로입니다.

단순 Pro는 종합모드와 별개인 한 번짜리 검토 경로입니다. 첨부된 계획·코드·문서를
검토하고 결과 파일을 반환하면 끝나며, 자동으로 구현이나 다음 단계로 넘어가지
않습니다. 계획부터 구현까지 이어야 할 때만 종합모드를 사용합니다.

Local Multi-GPT와 Web Multi-GPT는 서로 다른 경로입니다. Local Multi-GPT는
PC의 Codex 하위 레인을 사용하는 선택적 자문 도구이며, 모든 단계가
`gpt-5.6-luna`와 `max` 사고 레벨로 고정됩니다. 다른 모델이나 사고
레벨을 요청하면 하위 프로세스를 시작하기 전에 거부합니다. Web Multi-GPT는
Oracle이 여러 독립 ChatGPT 웹 세션을 실행한 뒤 결과를 병합합니다.

위 표에서 Oracle 기반 모드는 모두 선택적 로컬 경로입니다. cloud 실패를
로컬 경로로 자동 우회하지 않습니다.

## 요구사항

Cloud 기본 경로:

- GitHub에 동기화된 저장소
- 해당 저장소에 접근 가능한 Codex Cloud 환경
- 저장소별 `AGENTS.md`와 cloud-compatible test/CI

선택적 로컬 경로:

- Windows 11
- Python
- Node.js 22.19 이상, 27 미만
- Git for Windows / Git Bash
- Tailscale
- 브라우저에서 ChatGPT에 로그인된 Oracle 프로필
- ChatGPT Developer Mode에 최초 한 번 수동 등록한 DevSpace 앱

현재 검증된 조합은 Oracle `0.16.1`과 DevSpace `1.0.4`입니다. 설치기는
정확한 파일 해시가 일치할 때만 Windows 호환 패치를 적용합니다.

## 선택적 Windows 경로 설치

```powershell
git clone https://github.com/ventianima-lab/codexpro-automation.git
cd codexpro-automation
.\install.ps1 -WhatIf
.\install.ps1
```

설치기는 기존 파일을 백업하고
`%USERPROFILE%\.codex\receipts`에 설치 영수증을 남깁니다.

## 선택적 DevSpace 최초 연결

DevSpace 앱은 프로젝트마다 설치하는 것이 아닙니다. 앱 하나에 허용할
프로젝트 루트를 여러 번 `--root`로 지정합니다.

```powershell
python skills/chatgpt-workspace-setup/scripts/devspace_tailscale_setup.py setup `
  --root C:\projects\alpha `
  --root C:\projects\beta `
  --hostname your-device.your-tailnet.ts.net `
  --public-port 8443 `
  --dry-run
```

내용을 확인한 뒤 `--dry-run`을 `--apply`로 바꿉니다. ChatGPT Developer
Mode에는 다음 앱 하나만 수동으로 등록합니다.

- 이름: `DevSpace`
- URL: `https://your-device.your-tailnet.ts.net:8443/mcp`

Owner 승인을 완료한 뒤에는 매 작업마다 앱 목록·권한·URL을 다시 확인하거나
앱을 재등록하지 않습니다. 새 프로젝트는 DevSpace 허용 루트에만 추가합니다.
ChatGPT 설정·앱 목록·권한·삭제·선택 UI를 자동화하지 않습니다.

자세한 과정은
[DevSpace + Tailscale 설정](docs/DEVSPACE_TAILSCALE_SETUP.md)을
참고하세요.

## 일반 GPT 실행 예시

프로젝트 안에 UTF-8 미션 파일을 만든 뒤 먼저 미리보기 합니다.

```powershell
python "$env:USERPROFILE\.codex\bin\chatgpt_oracle_dispatch.py" `
  --mode orchestrator `
  --project-root C:\project `
  --mission-path C:\project\mission.md `
  --manifest-output C:\project\.ai-bridge\oracle.json `
  --reasoning-level "Very High" `
  --dry-run
```

실제 실행 승인이 있을 때만 `--dry-run`을 제거합니다.

## Luna 연속 지휘모드

`$luna-web-supervisor`는 기존 `$web-gpt`와 분리된 명시 호출형 경로입니다.
Codex 작업은 실제 `gpt-5.6-luna` + `high`여야 하며 제품 소스를 수정하지
않습니다. Luna는 한 번에 Web GPT 실행 하나만 제출·복구하고, 결과의 Git
경계와 선언된 테스트를 확인한 뒤 기존 Notion 기록을 readback합니다.

원본 checkout이 dirty이면 원본을 stash·reset하지 않습니다. 사용자가 별도
Luna 작업을 승인한 경우 현재 변경을 포함하는 `working-tree` 시작 상태의
Codex worktree task로 격리한 뒤 clean boundary에서 진행합니다. Notion 주소를
자동으로 채우라고 요청한 경우에는 같은 Project에 연결되고 AI 접근이 허용된
유일한 기존 Task·Report를 사용합니다. Luna의 effort는 `high`이고,
`Extra High`는 Web GPT Sol 화면에만 적용됩니다.

Oracle 상태의 `mode=browser`는 하위 브라우저 실행기이고,
`dispatch_mode=orchestrator`가 상위 지휘 계약입니다. 두 값을 서로 바꾸어
판정하지 않습니다. 로그인 전용 프로필이 초기화되지 않아 composer 이전에
실패한 경우에는 incident 분류가 실제 미제출을 입증한 뒤에만 현재 시도를
`PRE_SUBMIT_FAILED`로 보존하고 새 예약을 허용합니다. 같은 실행을 재제출하지
않습니다.

검증이 실패하면 Luna가 직접 고치지 않습니다. 실패 로그·현재 commit·허용
파일을 고정한 개선 미션을 만들고, 실패 기록을 Notion에서 다시 읽은 뒤 새
Web GPT 실행으로 원인 판단과 수정·테스트·commit을 요청합니다. 단위별
`max_web_attempts`와 전체 제출 상한을 manifest에 미리 적어 무한 반복을
막습니다. 자세한 계약과 명령은
[`skills/luna-web-supervisor/SKILL.md`](skills/luna-web-supervisor/SKILL.md)에
있습니다.

## Pro 실행 예시

Pro는 프로젝트 앱을 사용하지 않습니다. 미션과 필요한 증거 파일을 정확한
해시로 고정해 첨부합니다.

```powershell
python "$env:USERPROFILE\.codex\bin\chatgpt_oracle_dispatch.py" `
  --mode pro `
  --project-root C:\project `
  --mission-path C:\project\pro.md `
  --attachment C:\project\evidence.zip `
  --manifest-output C:\project\.ai-bridge\pro.json `
  --dry-run
```

## 실행과 복구 원칙

- 같은 프로젝트에는 활성 또는 불확실한 Oracle 작업 하나만 허용합니다.
- 다른 프로젝트는 서로 분리된 프로필로 병렬 실행할 수 있습니다.
- Web Multi-GPT는 하나의 부모 작업 안에서 최대 5개 세션씩 wave로 실행합니다.
- 비Pro의 무거운 작업은 1차 90분과 복구 90분, 실효 약 180분까지 기다립니다.
- 브라우저나 로컬 프로세스 종료는 웹 작업 실패의 증거가 아닙니다.
- 복구는 저장된 정확한 Oracle slug와 대화 URL만 사용하며 재제출하지 않습니다.
- 완료에는 Oracle 종료 코드 0과 비어 있지 않은 새 결과 파일이 모두 필요합니다.

정확한 실행을 회수하려면:

```powershell
python "$env:USERPROFILE\.codex\bin\chatgpt_oracle_run.py" recover `
  --run-dir C:\exact\oracle-run `
  --action harvest
```

## 업데이트와 제거

```powershell
.\install.ps1 -WhatIf
.\install.ps1
.\rollback.ps1
.\uninstall.ps1
```

기존에 저장된 구형 실행을 복구해야 하는 컴퓨터에서만
`-InstallLegacyRecoveryDependency`를 사용합니다.

## 문서

- [PC 독립 Cloud-first 운영](docs/CLOUD_FIRST_OPERATIONS.md)
- [전역 ChatGPT 라우팅과 모드 선택](docs/GLOBAL_CHATGPT_ROUTING.md)
- [DevSpace + Tailscale 최초 설정](docs/DEVSPACE_TAILSCALE_SETUP.md)
- [기술 변경 기록](docs/CHANGELOG.md)
- [구형 실행 복구용 동결 자산](docs/FROZEN_LEGACY.md)
- [릴리스 검증 절차](docs/RELEASE_CHECKLIST.md)
- [보안 정책](SECURITY.md)
- [제3자 라이선스](THIRD_PARTY_NOTICES.md)

## 레거시 호환

과거 CodexPro·agbrowse 기반 실행 파일은 이미 저장된 구형 작업을 원래
실행 신원으로 정확히 복구하기 위해서만 남아 있습니다. 새 작업의 실행 경로나 fallback으로 사용하지
않습니다. 상세 파일 목록은 [동결 자산 문서](docs/FROZEN_LEGACY.md)에
분리했습니다.

## 라이선스

MIT License. Oracle·DevSpace 등 제3자 구성요소의 저작권과 라이선스는
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)에 정리되어 있습니다.
