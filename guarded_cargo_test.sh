#!/usr/bin/env bash
set -u

limit_mb="${CARGO_TEST_MEM_LIMIT_MB:-4096}"
interval="${CARGO_TEST_MEM_POLL_SECS:-1}"

if [ "$#" -eq 0 ]; then
  set -- cargo test
fi

"$@" &
root="$!"

descendants() {
  ps -axo pid=,ppid= | awk -v root="$root" '
    {
      pid = $1
      ppid = $2
      parent[pid] = ppid
      seen[pid] = 1
    }
    END {
      print root
      for (pid in seen) {
        p = pid
        while (p in parent) {
          if (parent[p] == root) {
            print pid
            break
          }
          if (parent[p] == p || parent[p] == 0) {
            break
          }
          p = parent[p]
        }
      }
    }
  '
}

kill_tree() {
  pids="$(descendants | sort -rn | tr '\n' ' ')"
  kill -TERM $pids 2>/dev/null || true
  sleep 2
  kill -KILL $pids 2>/dev/null || true
}

while kill -0 "$root" 2>/dev/null; do
  pids_space="$(descendants | sort -n | tr '\n' ' ')"
  pids_csv="$(printf '%s\n' $pids_space | paste -sd, -)"
  rss_kb="$(ps -o rss= -p "$pids_csv" 2>/dev/null | awk '{sum += $1} END {print sum + 0}')"
  rss_mb="$(( (rss_kb + 1023) / 1024 ))"

  if [ "$rss_mb" -gt "$limit_mb" ]; then
    echo "guarded-cargo-test: RSS ${rss_mb} MiB exceeded limit ${limit_mb} MiB; killing process tree rooted at ${root}" >&2
    kill_tree
    wait "$root" 2>/dev/null
    exit 137
  fi

  sleep "$interval"
done

wait "$root"
