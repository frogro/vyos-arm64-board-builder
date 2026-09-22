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
