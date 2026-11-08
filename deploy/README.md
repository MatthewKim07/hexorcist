# Deploying on a Vultr VM

Tested assumption: a fresh Ubuntu 24.04 VM with 4 vCPU and 8 GB RAM. All images build on the VM itself, which takes several minutes the first time because the sandbox image compiles simavr and downloads the AVR toolchain.

## Before you start

1. Push the branch you want to deploy. The VM clones from GitHub.
2. Create the VM in the Vultr console and note its IP. Add your SSH key when you create it.

## 1. Set up the VM

SSH in as root, then:

```bash
curl -fsSL https://raw.githubusercontent.com/MatthewKim07/hexorcist/hexorcist-mvp/deploy/bootstrap.sh -o bootstrap.sh
less bootstrap.sh    # read it before running it as root
bash bootstrap.sh
```

This installs Docker from Docker's own repository, turns on ufw allowing only 22, 80 and 443, and clones the repo to `/opt/hexorcist`.

## 2. Create `.env`

Your keys never leave this file. Editing it in `nano` keeps them out of your shell history.

```bash
cd /opt/hexorcist
cp deploy/env.production.example .env
chmod 600 .env
openssl rand -base64 18    # copy this for DEMO_PASSCODE
nano .env
```

Fill in:

| Variable | Value |
| --- | --- |
| `LLM_BASE_URL` | `https://api.vultrinference.com/v1` (already filled in) |
| `LLM_API_KEY` | Your Vultr Serverless Inference key |
| `LLM_MODEL` | Leave empty for now, the next step lists the choices |
| `DEMO_PASSCODE` | The value `openssl` just printed. Anyone starting a run needs it |
| `ACME_EMAIL` | Your email. It also turns on Caddy's ZeroSSL certificate failover |

Then list the models your key can use. This prints model ids and never the key:

```bash
deploy/list-models.sh
```

Paste a chat model's id into `LLM_MODEL` with `nano .env`. The list may include embedding or speech models, which will not work here.

## 3. Start

```bash
deploy/up.sh
```

It prints your URL, which comes from the VM's IP: `203.0.113.5` becomes `https://203-0-113-5.sslip.io`. The first certificate can take a minute.

## 4. Smoke test

```bash
deploy/smoke-test.sh                  # everything, about 10 minutes, spends LLM tokens
deploy/smoke-test.sh --skip-presets   # everything except the LLM runs
```

It saves its output to `smoke-results-<time>.txt` and checks, in order:

1. Valid HTTPS, `/api/health`, LLM configured, Vultr in use, passcode required, rate limit on.
2. HTTP redirects to HTTPS, a run without the passcode is refused, only 22, 80 and 443 are open, ufw is active, and only the backend holds the Docker socket.
3. `verify_sandbox` on this kernel.
4. Emulation speed on this VM, alone and with all sandboxes busy.
5. The containment preset through the public URL, which needs no LLM.
6. All presets with the real model through the public URL.

## What protects the public demo

| Control | How |
| --- | --- |
| HTTPS | Caddy, certificates renew automatically |
| Passcode | Required. The backend and compose both refuse to start without one |
| Passcode guessing | 20 wrong tries per IP per hour, then 429 |
| Rate limits | `RATE_LIMIT_PER_HOUR` runs per IP, `MAX_ACTIVE_RUNS` at once |
| Firewall | ufw allows 22, 80 and 443 |
| Published ports | Only Caddy publishes any. Docker's published ports bypass ufw, so ufw alone would not be enough |
| Docker socket | Backend only, never a sandbox, and checked by the smoke test |

Reads are not behind the passcode, because a browser's EventSource cannot send headers. Anyone with the URL can read past runs, so do not upload anything private to a public demo.

## If something goes wrong

**No certificate.** Check `deploy/compose.sh logs caddy`. All of sslip.io shares one Let's Encrypt limit, and it has been exhausted before. Caddy fails over to ZeroSSL by itself, and keeps retrying. If both refuse, point any domain you own at the VM, or try nip.io, and restart with that name:

```bash
SITE_HOST=demo.example.com deploy/up.sh
```

Export `SITE_HOST` for later `deploy/compose.sh` commands too, or it goes back to sslip.io. Certificates are kept in a Docker volume, so do not delete `caddy-data` needlessly.

**`deploy/list-models.sh` fails.** Check the key in the Vultr console. The console's Serverless Inference page also shows the model list.

**The smoke test cannot reach its own URL.** Some networks do not route a VM back to its own public address. Check the URL from your laptop, then run `SMOKE_API=http://frontend:80 deploy/smoke-test.sh`.

**Emulation is too slow.** `measure_speed` says so. Set `SANDBOX_MAX_PARALLEL=2` in `.env` or use a faster VM.

## Later updates

```bash
cd /opt/hexorcist
git pull --ff-only
deploy/up.sh
```

Update the running LLM settings by editing `.env`, then `deploy/compose.sh up -d --force-recreate backend`.

## Clean up

Destroying the VM in the Vultr console removes everything on it. Delete the inference key separately if you are done with it.
