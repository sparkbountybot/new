# Auto-pull shared notes (add this to your shell init or call before working)
pull_shared_notes() {
    cd /sandbox/new 2>/dev/null || return
    git -C /sandbox/new pull origin main 2>/dev/null
}
