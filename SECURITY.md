# 보안 정책

보안 취약점은 이 저장소의 GitHub **Security** 탭에서 비공개 취약점 신고로 알려 주세요.

공개 Issue에는 다음 정보를 올리지 마세요.

- `codexpro_token`이나 기타 접근 토큰
- ChatGPT·GitHub·Cloudflare·ngrok 계정 정보
- 브라우저 프로필, 쿠키, 로그인 상태
- 개인용 전체 MCP URL
- DevSpace Owner 비밀번호, OAuth token, 허용 root 목록
- 프롬프트·응답·로그에 포함된 비공개 소스 코드나 개인정보

재현에 로그가 필요하면 비밀 값을 삭제하거나 `<redacted>`로 바꾼 최소 재현 자료만 첨부해 주세요.

Cloud 기본 경로에서는 GitHub commit/branch가 유일한 소스 정본입니다. 로컬
dirty working tree를 자동 업로드하지 않으며, 공개 저장소에 secret·원본
자격 증명·브라우저 상태·개인정보·machine-only 경로를 넣지 않습니다.
Codex Cloud 환경 secret은 setup 단계에서만 사용하고 agent 단계에서 필요한
일반 설정값과 분리합니다. Agent internet access는 기본적으로 끄고, 필요한
도메인과 HTTP method만 최소 범위로 허용합니다.

Cloud 완료는 원격 branch/PR과 exact commit CI로 판단합니다. Bridge, Funnel,
Worker, 로컬 프로세스의 HTTP 200은 cloud 권한이나 실행 완료를 증명하지
않습니다.

DevSpace는 허용한 프로젝트에서 로컬 사용자 권한으로 파일과 명령을
다룹니다. 드라이브 루트 전체를 허용하지 말고 필요한 프로젝트만
등록하세요. Tailscale Funnel은 공개 인터넷 endpoint이므로 Tailnet
정책, HTTPS, hostname과 공개 범위를 먼저 확인해야 합니다. 평상시 GPT
실행은 Funnel이나 ChatGPT 앱 설정을 변경하지 않습니다.
