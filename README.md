# AutoClicker

A small desktop app that clicks spots on your screen, in order, until you pause it or close it. You can keep five setups, change the play/pause key, and drag a speed bar. Setups are saved on this PC and loaded the next time you open the app. Minimizing the window does not stop the clicks.

## Open it

Download this folder and open it. Double-click the **AutoClicker** icon (`AutoClicker.exe`). The icon is the purple pointer.

The first time, that icon sets up Python in a `.venv` folder beside it, then the window opens. The next time, the icon opens the window directly.

Install Python 3.11 or newer from [python.org](https://www.python.org/downloads/) and check **Add python.exe to PATH** before the first open. Windows may ask you to confirm the program the first time. Choose **More info**, then **Run anyway**.

`run.bat` starts the same app if you prefer that.

You can also do it yourself:

```bat
py -3 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## One file you can copy

On the PC where you want the program, from this folder:

```bat
pip install -r requirements.txt pyinstaller
python scripts/build.py
```

That writes `dist\AutoClicker.exe`. Copy that file anywhere and double-click it. No Python window is left open.

A GitHub Actions build also uploads `AutoClicker-Windows` from this repo's Actions tab when the workflow runs.

## macOS and Linux

Double-click `AutoClicker.desktop`, or run:

```bash
chmod +x run.sh AutoClicker.desktop
./run.sh
```

macOS will ask for Accessibility permission the first time the app clicks or listens for the play/pause key. On Linux, use an X11 session. Wayland desktops usually block this kind of global click.

## How to use it

1. The window opens on **set 1**. The set in use is filled in purple.
2. Click a set number, or click **Set up clicks**. Empty sets ask you to set them up.
3. Choose how many clicks that set should run, from 1 to 5.
4. Click the spot on your screen for click 1. Confirm it, or pick again. Then do the same for the next spot.
5. After the last confirm, the set is saved.
6. Press **Play**, or the play/pause key (F6 until you change it). Clicks run in order, then start again, until you pause or close the app. The stop key (F8 until you change it) only pauses.
7. Drag the speed bar toward **Fast** to shorten the gap between clicks.
8. **Edit** on a saved spot to move just that click. **Set up again** replaces the whole set. Cancel keeps what you already saved.
9. **Change** next to a key, then press the new key. **Save** stores it. Esc or **Cancel** keeps the previous key. Play and stop cannot be the same key.
10. Minimize keeps the clicks going. Close stops them.

Switching to another set that already has spots uses that set on the next pass. The five sets, the key, and the speed are still there after you quit.

Settings are stored in:

- Windows: `%APPDATA%\AutoClicker\settings.json`
- macOS: `~/Library/Application Support/AutoClicker/settings.json`
- Linux: `~/.config/AutoClicker/settings.json`

Some games and sites do not allow auto-clickers. This app only clicks where you told it to, and only while it is running.

## Tests

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```
