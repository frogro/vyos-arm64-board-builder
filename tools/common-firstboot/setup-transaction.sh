# Sourced after the VyOS script-template; retain its configuration-mode aliases.
setup_set() {
    if ! set "$@"; then
        echo "ERROR: Configuration command failed; discarding this stage." >&2
        discard
        builtin exit 1
    fi
}

setup_commit_save() {
    # A repeated setup with no changes is successful, not a failed commit.
    if $API sessionChanged; then
        if ! commit; then
            discard
            return 1
        fi
    fi
    save
}

# Register only after configure succeeds: teardown affects this helper's session.
# Never commit here; failed stages must remain failed and be discarded by teardown.
setup_session_cleanup() {
    local result=$?
    trap - EXIT
    if ! "$API" teardownSession; then
        echo "ERROR: Could not close setup configuration session." >&2
        [ "$result" -ne 0 ] || result=1
    fi
    builtin exit "$result"
}

setup_session_guard() {
    trap setup_session_cleanup EXIT
}
