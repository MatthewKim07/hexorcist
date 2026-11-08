#!/bin/bash
# Sandbox entrypoint. Reads a tar of inputs from stdin into /work, does one job,
# and prints a single JSON document on stdout. Everything else goes to files so
# untrusted output can never corrupt that document.
set -u

MODE="${1:-}"
export HOME=/work
export TMPDIR=/tmp

case "$MODE" in
    compile)
        mkdir -p /work/in /work/build /work/out
        tar -xf - -C /work/in
        mkdir -p /work/sketch
        cp /work/in/sketch.ino /work/sketch/sketch.ino
        arduino-cli --config-file /etc/arduino-cli.yaml compile \
            --fqbn arduino:avr:uno \
            --jobs 2 \
            --warnings default \
            --build-path /work/build \
            --output-dir /work/out \
            /work/sketch >/work/compile.log 2>&1
        rc=$?
        : >/work/elf.b64
        if [ "$rc" -eq 0 ] && [ -f /work/out/sketch.ino.elf ]; then
            base64 -w0 /work/out/sketch.ino.elf >/work/elf.b64
        fi
        jq -n --argjson rc "$rc" --rawfile log /work/compile.log --rawfile elf /work/elf.b64 \
            '{ok: ($rc == 0), exit_code: $rc, log: $log, elf_b64: $elf}'
        ;;
    run)
        mkdir -p /work/in
        tar -xf - -C /work/in
        extra=""
        if [ -f /work/in/no_sim_cap ]; then
            extra="--no-sim-cap"
        fi
        # shellcheck disable=SC2086
        hexharness --elf /work/in/fw.elf --scenario /work/in/scenario.json \
            --out /work/result.json $extra >/work/harness.log 2>&1
        rc=$?
        if [ "$rc" -eq 0 ] && [ -f /work/result.json ]; then
            cat /work/result.json
        else
            jq -n --argjson rc "$rc" --rawfile log /work/harness.log \
                '{harness_error: true, exit_code: $rc, log: $log}'
            exit "$rc"
        fi
        ;;
    probe)
        # Reports what a program inside this sandbox can actually see and reach.
        cat >/dev/null
        net="blocked"
        if bash -c 'exec 3<>/dev/tcp/1.1.1.1/53' 2>/dev/null; then
            net="reachable"
        fi
        dns="blocked"
        if getent hosts vultr.com >/dev/null 2>&1; then
            dns="resolved"
        fi
        rootfs="read-only"
        if touch /hexorcist-write-test 2>/dev/null; then
            rootfs="writable"
        fi
        docker_sock="absent"
        if [ -e /var/run/docker.sock ] || [ -e /run/docker.sock ]; then
            docker_sock="present"
        fi
        ifaces=""
        for dev in /sys/class/net/*; do
            if [ -d "$dev" ] && [ "$(cat "$dev/operstate" 2>/dev/null)" != "down" ]; then
                ifaces="$ifaces $(basename "$dev")"
            fi
        done
        env_names=$(env | cut -d= -f1 | sort | tr '\n' ' ')
        # What an #include of these paths really hands the attacker: the sandbox's own files.
        passwd_users=$(cut -d: -f1 /etc/passwd | tr '\n' ' ')
        environ_names=$(cat /proc/self/environ | tr '\0' '\n' | cut -d= -f1 | sort | tr '\n' ' ')
        ssh_key="absent"
        if [ -e "$HOME/.ssh/id_rsa" ] || [ -e /root/.ssh/id_rsa ]; then
            ssh_key="present"
        fi
        cap_eff=$(grep CapEff /proc/self/status | awk '{print $2}')
        nnp=$(grep NoNewPrivs /proc/self/status | awk '{print $2}')
        jq -n \
            --arg uid "$(id -u)" \
            --arg user "$(id -un)" \
            --arg net "$net" \
            --arg dns "$dns" \
            --arg rootfs "$rootfs" \
            --arg docker_sock "$docker_sock" \
            --arg ifaces "$ifaces" \
            --arg env_names "$env_names" \
            --arg cap_eff "$cap_eff" \
            --arg no_new_privs "$nnp" \
            --arg passwd_users "$passwd_users" \
            --arg environ_names "$environ_names" \
            --arg ssh_key "$ssh_key" \
            '{uid: $uid, user: $user, network: $net, dns: $dns, rootfs: $rootfs,
              docker_sock: $docker_sock, interfaces: ($ifaces | split(" ") | map(select(. != ""))),
              env_names: ($env_names | split(" ") | map(select(. != ""))),
              cap_eff: $cap_eff, no_new_privs: $no_new_privs,
              etc_passwd_users: ($passwd_users | split(" ") | map(select(. != ""))),
              proc_environ_names: ($environ_names | split(" ") | map(select(. != ""))),
              ssh_key: $ssh_key}'
        ;;
    *)
        echo "usage: entry.sh compile|run|probe (tar on stdin)" >&2
        exit 2
        ;;
esac
