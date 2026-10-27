# Connect FOLIO to collectionHQ Academic

This guide takes a library from nothing to a weekly delivery to collectionHQ Academic, using [FOLIO-Exchange](https://github.com/ByYudkowskysTentacle/FOLIO-Exchange) and the `chq-academic` recipe. You run every step yourself, on a PC or server inside the library's network. Most of the elapsed time is waiting on your FOLIO administrator and on collectionHQ, so ask them for what step 1 lists first.

FOLIO-Exchange only reads from FOLIO, never reads user or patron records, and sends nothing to collectionHQ until you release the first delivery yourself.

1. [Gather](#1-gather-what-you-need) the FOLIO account and the collectionHQ SFTP details.
2. [Install](#2-install-folio-exchange) FOLIO-Exchange.
3. [Set up](#3-set-up-the-feed) the site and the `chq` feed with the guided setup.
4. [Build and check](#4-build-the-files-and-check-them) the files without sending them.
5. [Agree the files](#5-agree-the-files-with-collectionhq) with collectionHQ.
6. [Send](#6-the-first-delivery) the first delivery.
7. [Schedule](#7-schedule-it) the weekly run.

## 1. Gather what you need

### From your FOLIO administrator or hosting provider

1. **The API address.** On Eureka this is the Kong gateway URL, which is not the address of the FOLIO web pages. It starts with `https://`.
2. **The tenant id**, a short name such as `fs00001234`.
3. **A dedicated, read-only service account** with these permissions (on Eureka, the matching capabilities with view access, in a role given to the account):

   ```
   circulation-storage.loans.collection.get
   inventory-storage.call-number-types.collection.get
   inventory-storage.classification-types.collection.get
   inventory-storage.holdings.collection.get
   inventory-storage.identifier-types.collection.get
   inventory-storage.instances.collection.get
   inventory-storage.item-note-types.collection.get
   inventory-storage.items.collection.get
   inventory-storage.loan-types.collection.get
   inventory-storage.location-units.campuses.collection.get
   inventory-storage.location-units.institutions.collection.get
   inventory-storage.location-units.libraries.collection.get
   inventory-storage.locations.collection.get
   inventory-storage.material-types.collection.get
   source-storage.source-records.collection.get
   ```

   The loans permission gives loan counts and dates. FOLIO-Exchange drops the borrower from each loan as it arrives and never stores it.
4. **Your setup:** whether the library is a member of an ECS consortium (then set `srs_include_shared: true` under `folio:` in `site.yaml`), and whether your migration kept old loan counts or created dates in item notes, and under which note types.

Many FOLIO hosts accept API traffic only from known networks. Use a PC or server inside the library's network, or on its VPN, and keep it on at the scheduled time.

### From collectionHQ

Ask your collectionHQ implementation contact for:

1. **An SFTP account:** server name, user name and password.
2. **The folder** on the server for bibs and items.
3. **The server's host key fingerprint**, to compare with the one FOLIO-Exchange reads from the server.
4. Answers to the open points in [layout.md](layout.md#confirm-with-collectionhq), or at least the cadence.

What is known about collectionHQ's US server, as of October 2026:

| | |
| --- | --- |
| Server | `sftp.us.collectionhq.com`, port 22, an AWS Transfer Family server |
| Host key | RSA `SHA256:qt5HxgZ6ktlwhFUUAwdjMZlL2KkAbKXhy2TsRxWoITI`, read from the server on 26 Oct 2026. collectionHQ has not confirmed it, so compare it with theirs. A different value is a reason to stop and ask. |
| Not usable | `ftp.collectionhq.com` offers plain FTP only, which FOLIO-Exchange never uses |
| Accounts | Described as upload-only, so the recipe uploads straight to the final file names, with no rename. One library's account could still list its login folder, which held `holds/` and `transactions/`: those look like other collectionHQ feeds, so don't use them without asking |

### How passwords travel

- **To you:** through the library's password manager or a one-time share link, not by plain email, chat or a shared document.
- **To FOLIO-Exchange:** typed at its prompt, which does not show it. It goes straight into the system keyring (Windows Credential Manager on Windows), stored for your user account, and never into a file, a log, a report or a conversation with an AI assistant.
- **Nobody else needs them.** If someone is helping you, share the address, tenant id, user names and the output of the commands below. None of those contain a password.

## 2. Install FOLIO-Exchange

You need Python 3.10 or later (from python.org; on Windows it includes the `py` launcher) and Git. FOLIO-Exchange is not on PyPI yet, so it installs from GitHub. In PowerShell:

```powershell
py -3 -m venv C:\FOLIO-Exchange\venv
C:\FOLIO-Exchange\venv\Scripts\python -m pip install "folio-exchange @ git+https://github.com/ByYudkowskysTentacle/FOLIO-Exchange.git@main"
$env:Path = "C:\FOLIO-Exchange\venv\Scripts;" + $env:Path
folio-exchange --version
```

The `$env:Path` line makes the command available in this window; repeat it in each new window. On Linux, use `python3 -m venv /opt/folio-exchange/venv` and `/opt/folio-exchange/venv/bin/` in the same way.

FOLIO-Exchange ships a copy of the `chq-academic` recipe, so nothing else is needed. To use a recipe version from this repository before a FOLIO-Exchange release carries it, see [the recipe's notes](../recipes/chq-academic/README.md#using-a-version-before-folio-exchange-ships-it).

## 3. Set up the feed

Pick a folder for your library's settings, outside OneDrive or any synced folder, and run the guided setup:

```powershell
folio-exchange init C:\FOLIO-Exchange\mylibrary
```

| Question | Answer |
| --- | --- |
| FOLIO API address, tenant id, service account user name | from your FOLIO administrator |
| FOLIO password | typed at the prompt; stored in the keyring |
| Which vendor feed | collectionHQ Academic |
| A short name for this feed | `chq` (press Enter) |
| Leave out any locations | locations collectionHQ should not analyse, such as online resources or staff-only shelves. The list comes from your tenant |
| Leave out items with these statuses | none: collectionHQ analyses every status |
| Migrated item notes | yes only if the migration kept loan counts or dates in item notes; then pick those note types |
| Build a preview | `y` |
| How are the files delivered | **upload to the vendor's SFTP server**, if you have the account; otherwise **not yet**, and run `init` again when you do |
| SFTP server name, port | `sftp.us.collectionhq.com`, `22`, unless collectionHQ says otherwise |
| SFTP user name, folder on the server | from collectionHQ (`.` is the login folder) |
| Does the fingerprint match | **yes** only if it matches the one collectionHQ gave you. Without theirs yet, choose **I don't have the vendor's value yet**: FOLIO-Exchange keeps the key but never logs in to the server, and the feed stays paused, until you run `init` again and answer that it matches. If setup says delivery stays off (it could not reach the server), run `init` again later |
| SFTP password | typed at the prompt; stored in the keyring. Leave it blank to store it later with `folio-exchange secret set chq`; the feed stays paused until then |
| When should it run | `manual` for now; step 7 sets the schedule |
| Alerts | email, or a Slack or Teams webhook, for failed runs |

If setup stops at the permissions step, it lists exactly which permissions are missing. Send that list to your FOLIO administrator and run the same `init` command again later; your answers so far are kept.

The setup writes `site.yaml` and `feeds\chq.yaml` in the folder. [examples/feeds/chq.yaml](../examples/feeds/chq.yaml) is a commented copy of a collectionHQ feed file, if you prefer to edit settings by hand. To leave out `-s C:\FOLIO-Exchange\mylibrary` in the commands below, set it once for your Windows user, then open a new window:

```powershell
setx FOLIO_EXCHANGE_SITE C:\FOLIO-Exchange\mylibrary
```

## 4. Build the files and check them

```powershell
folio-exchange check
folio-exchange preview chq
folio-exchange run chq --no-deliver
```

- `check` logs in, tests every endpoint the recipe needs and shows record counts. `check --delivery` logs in to collectionHQ's server and lists the folder, without uploading anything. While the key is unconfirmed it does not log in; it shows the server's current key next to the stored one.
- `preview` builds files from a small sample and prints a few item rows.
- `run --no-deliver` downloads everything into the local cache and builds the full files. The first run fetches the whole catalogue: on FOLIO's reference system, 10,000 bibs with their MARC took 30 seconds, so 300,000 might take around a quarter of an hour, depending on your host. Later runs fetch only what changed.

The files land in `C:\FOLIO-Exchange\mylibrary\out\chq\<date-time>\`, with `run-report.json` beside them. `folio-exchange history` lists the runs, and `folio-exchange ui` shows them in your browser. Look at:

- **Counts:** bibs and items written, and items left out with the reason. Do they match what you expect from FOLIO?
- **The item file:** open a copy in Excel (Data > From Text/CSV, delimiter `|`) or a text editor. Are location names right? Do items show a call number?
- **The bib file:** open it in MarcEdit. Each record's 999 ff $i is the instance UUID that the item rows' `Bib record ID` repeats.
- **A few items you know well:** last checkout, status, location, call number and loan counts, against the FOLIO Inventory app. Twenty is a good sample.

If an item row looks wrong, check the column against [layout.md](layout.md), which says where each value comes from.

## 5. Agree the files with collectionHQ

Send your implementation contact:

- the layout page, from `folio-exchange recipes summary chq`, which shows the recipe's layout with any column or format changes in your feed, and the schedule;
- the locations you leave out, and any legacy note types you use, which the layout page does not list;
- the two files from the run in step 4, zipped, so the MARC survives email intact;
- your questions from [layout.md](layout.md#confirm-with-collectionhq).

Change local settings in `feeds\chq.yaml` as they answer: the folder (`delivery.remote_dir`), the host key, filters, or the item file's columns and formats under `outputs.items`. Run `folio-exchange check` after every edit, and `run chq --no-deliver` to see the result. A change collectionHQ wants from every library belongs in the recipe instead: [open an issue](https://github.com/ByYudkowskysTentacle/FOLIOHQ/issues).

## 6. The first delivery

When collectionHQ has confirmed the folder and the host key, and the files look right:

```powershell
folio-exchange init C:\FOLIO-Exchange\mylibrary   # only if the key was unconfirmed: answer that it matches
folio-exchange feeds resume chq          # if the feed is still paused
folio-exchange check --delivery
folio-exchange run chq
folio-exchange release chq
```

If setup said delivery stays off, run `folio-exchange init` again first: with delivery off, `run` builds the files and sends nothing. `run` syncs, builds and checks the files, then holds them: the first delivery to a destination always waits for a person. `release` shows the run, its counts, the files and where they will go, checks that the files are unchanged since the build, and sends them once you confirm. Tell collectionHQ the files are there and ask them to confirm they loaded.

## 7. Schedule it

```powershell
folio-exchange schedule
```

It prints the one command that registers an hourly Windows scheduled task (or a cron line on Linux) which runs `folio-exchange run --due`. Run that command yourself; on Windows, run it in a Command Prompt (cmd.exe), not PowerShell, whose quoting rules break it. Then set the feed's schedule, for example `schedule: Sun 03:30` in `feeds\chq.yaml`, after agreeing the day and cadence with collectionHQ.

- The task must run as the Windows user who stored the passwords, because keyring entries belong to that user. The printed command does this, and asks for that user's Windows password for Task Scheduler.
- A missed slot (the PC was off) runs at the next hourly start.
- On Linux under cron or systemd there is often no keyring session: use `secret: env:NAME` in the files and an environment file instead.

## When something goes wrong

| What you see | What to do |
| --- | --- |
| `Cannot reach FOLIO at …` | Check the API address, and that the PC is on the library network or VPN. |
| `FOLIO refused the login …` | Check the user name and tenant id; store the password again with `folio-exchange secret set folio`. A refused password is tried only once per run, so it cannot lock the account. |
| `DENIED … the account lacks …` | Send the listed permissions to your FOLIO administrator. |
| A run is **blocked** | The item count fell below 90% of the last delivery, or rows are missing a required value. The message says which check failed and gives the counts. If FOLIO is wrong, fix it and run again; if the drop is real (a big weed), `release chq` sends the blocked run after you confirm. |
| The SFTP login fails | Test with `folio-exchange check --delivery`; store the password again with `folio-exchange secret set chq`. |
| A host key mismatch | Stop and ask collectionHQ. A changed key can mean the wrong server. |

Every run is recorded: `folio-exchange history` lists runs, `history --show <number>` shows one in full, and `history --audit` shows who changed, released or upgraded what. For a FOLIO-Exchange problem that is not about collectionHQ, open an issue in [FOLIO-Exchange](https://github.com/ByYudkowskysTentacle/FOLIO-Exchange/issues).

## Moving from the legacy tool

A library running `folio-chq-extract` follows the same steps. [legacy/README.md](../legacy/README.md#moving-to-folio-exchange) lists what carries over and what to set up again.
