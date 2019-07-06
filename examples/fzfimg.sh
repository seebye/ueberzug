#!/usr/bin/env bash
readonly BASH_BINARY="$(which bash)"
readonly REDRAW_COMMAND="toggle-preview+toggle-preview"
declare -r -x REDRAW_KEY="µ"
declare -r -x UEBERZUG_FIFO="$(mktemp --dry-run --suffix "fzf-$$-ueberzug")"
declare -r -x PREVIEW_ID="preview"
declare -r -x PREVIEW_POSITION="right"
declare -r -x PREVIEW_WIDTH="70%"


function start_ueberzug {
    mkfifo "$UEBERZUG_FIFO"
    ueberzug layer --parser bash --silent <"$UEBERZUG_FIFO" &
    # prevent EOF
    exec 3>"$UEBERZUG_FIFO"
}


function finalise {
    exec 3>&-
    rm "$UEBERZUG_FIFO" &>/dev/null
    kill $(jobs -p)
}


function calculate_position {
    # TODO costs: creating processes > reading files
    #      so.. maybe we should store the terminal size in a temporary file
    #      on receiving SIGWINCH
    #      (in this case we will also need to use perl or something else
    #      as bash won't execute traps if a command is running)
    < <(</dev/tty stty size) \
        read TERMINAL_LINES TERMINAL_COLUMNS

    case "$PREVIEW_POSITION" in
        left|up|top)
            X=1
            Y=1
            ;;
        right)
            X=$((TERMINAL_COLUMNS - COLUMNS - 2))
            Y=1
            ;;
        down|bottom)
            X=1
            Y=$((TERMINAL_LINES - LINES - 1))
            ;;
    esac
}


function on_selection_changed {
    calculate_position

    >"${UEBERZUG_FIFO}" declare -A -p cmd=( \
        [action]=add [identifier]="${PREVIEW_ID}" \
        [x]="$X" [y]="$Y" \
        [width]="$COLUMNS" [height]="$LINES" \
        [scaler]=forced_cover [scaling_position_x]=0.5 [scaling_position_y]=0.5 \
        [path]="$@")
        # add [synchronously_draw]=True if you want to see each change
}


function print_on_winch {
    # print "$@" to stdin on receiving SIGWINCH
    # use exec as we will only kill direct childs on exiting,
    # also the additional bash process isn't needed
    </dev/tty \
        exec perl -e '
            while (1) {
                local $SIG{WINCH} = sub {
                    ioctl(STDIN, 0x5412, $_) for split "", join " ", @ARGV;
                };
                sleep;
            }' \
            "$@"
}


if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    trap finalise EXIT
    # print the redraw key twice as there's a run condition we can't circumvent
    # (we can't know the time fzf finished redrawing it's layout)
    print_on_winch "${REDRAW_KEY}${REDRAW_KEY}" &
    start_ueberzug

    export -f on_selection_changed calculate_position
    SHELL="$BASH_BINARY" \
        fzf --preview "on_selection_changed {}" \
            --preview-window "${PREVIEW_POSITION}:${PREVIEW_WIDTH}" \
            --bind "$REDRAW_KEY":"$REDRAW_COMMAND"
fi
