/* Starts AutoClicker from the folder this program sits in.
   First launch creates .venv and installs requirements. Later launches open the window. */

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <shellapi.h>
#include <string.h>

static void module_dir(wchar_t *dir, DWORD cap) {
    DWORD length = GetModuleFileNameW(NULL, dir, cap);
    if (length == 0 || length >= cap) {
        dir[0] = L'\0';
        return;
    }
    wchar_t *slash = wcsrchr(dir, L'\\');
    if (slash) {
        *slash = L'\0';
    }
}

static int exists_file(const wchar_t *path) {
    DWORD attributes = GetFileAttributesW(path);
    return attributes != INVALID_FILE_ATTRIBUTES && (attributes & FILE_ATTRIBUTE_DIRECTORY) == 0;
}

static int assign(wchar_t *out, size_t cap, const wchar_t *text) {
    size_t length = wcslen(text);
    if (length + 1 > cap) {
        return 0;
    }
    memcpy(out, text, (length + 1) * sizeof(wchar_t));
    return 1;
}

static int append(wchar_t *out, size_t cap, const wchar_t *text) {
    size_t length = wcslen(out);
    size_t extra = wcslen(text);
    if (length + extra + 1 > cap) {
        return 0;
    }
    memcpy(out + length, text, (extra + 1) * sizeof(wchar_t));
    return 1;
}

static int run_and_wait(wchar_t *command, const wchar_t *dir) {
    STARTUPINFOW startup;
    PROCESS_INFORMATION process;
    ZeroMemory(&startup, sizeof(startup));
    startup.cb = sizeof(startup);
    ZeroMemory(&process, sizeof(process));
    if (!CreateProcessW(NULL, command, NULL, NULL, FALSE, 0, NULL, dir, &startup, &process)) {
        return 0;
    }
    WaitForSingleObject(process.hProcess, INFINITE);
    DWORD code = 1;
    GetExitCodeProcess(process.hProcess, &code);
    CloseHandle(process.hProcess);
    CloseHandle(process.hThread);
    return code == 0;
}

static void tell(const wchar_t *text) {
    MessageBoxW(NULL, text, L"AutoClicker", MB_OK | MB_ICONINFORMATION);
}

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE previous, LPWSTR command, int show) {
    (void)instance;
    (void)previous;
    (void)command;
    (void)show;

    wchar_t dir[MAX_PATH];
    module_dir(dir, MAX_PATH);
    if (dir[0] == L'\0') {
        tell(L"AutoClicker could not find its folder.");
        return 1;
    }

    wchar_t python[MAX_PATH];
    wchar_t pythonw[MAX_PATH];
    wchar_t pynput[MAX_PATH];
    if (!assign(python, MAX_PATH, dir) || !append(python, MAX_PATH, L"\\.venv\\Scripts\\python.exe") ||
        !assign(pythonw, MAX_PATH, dir) || !append(pythonw, MAX_PATH, L"\\.venv\\Scripts\\pythonw.exe") ||
        !assign(pynput, MAX_PATH, dir) ||
        !append(pynput, MAX_PATH, L"\\.venv\\Lib\\site-packages\\pynput\\__init__.py")) {
        tell(L"This folder path is too long for AutoClicker to start.");
        return 1;
    }

    if (!exists_file(python)) {
        wchar_t setup[1024];
        int created = assign(setup, 1024, L"py -3 -m venv \"") && append(setup, 1024, dir) &&
            append(setup, 1024, L"\\.venv\"");
        if (!created) {
            tell(L"This folder path is too long for AutoClicker to start.");
            return 1;
        }
        if (!run_and_wait(setup, dir)) {
            created = assign(setup, 1024, L"python -m venv \"") && append(setup, 1024, dir) &&
                append(setup, 1024, L"\\.venv\"");
            if (!created) {
                tell(L"This folder path is too long for AutoClicker to start.");
                return 1;
            }
            if (!run_and_wait(setup, dir) || !exists_file(python)) {
                tell(L"AutoClicker needs Python 3.11 or newer.\n\n"
                     L"Install it from python.org and check \"Add python.exe to PATH\", then open this icon again.");
                return 1;
            }
        }
    }

    if (!exists_file(pynput)) {
        wchar_t pip[1024];
        if (!assign(pip, 1024, L"\"") || !append(pip, 1024, python) ||
            !append(pip, 1024, L"\" -m pip install -r requirements.txt")) {
            tell(L"This folder path is too long for AutoClicker to start.");
            return 1;
        }
        if (!run_and_wait(pip, dir) || !exists_file(pynput)) {
            tell(L"AutoClicker could not finish setup.\n\n"
                 L"Check that this PC is online, then open this icon again.");
            return 1;
        }
    }

    const wchar_t *runner = exists_file(pythonw) ? pythonw : python;
    wchar_t script[MAX_PATH + 8];
    if (!assign(script, MAX_PATH + 8, L"\"") || !append(script, MAX_PATH + 8, dir) ||
        !append(script, MAX_PATH + 8, L"\\main.py\"")) {
        tell(L"This folder path is too long for AutoClicker to start.");
        return 1;
    }
    HINSTANCE started = ShellExecuteW(NULL, L"open", runner, script, dir, SW_SHOWNORMAL);
    if ((INT_PTR)started <= 32) {
        tell(L"AutoClicker could not open its window.");
        return 1;
    }
    return 0;
}
