# El Jefe de los HURCs

El Jefe is the device used to distribute the latest team names and controller addresses to nearby HURC controllers. You only need to update **El Jefe**; you do **not** need to upload new firmware to every controller when the team list changes.

## What you need

- El Jefe ESP32 device and a USB cable
- A computer with [Visual Studio Code](https://code.visualstudio.com/) and the [PlatformIO IDE extension](https://platformio.org/install/ide?install=vscode)
- Python 3 installed
- The latest CSV export of the **HURC ESP32 Mac Address** Google Sheet
- The controllers you want to update, powered on and nearby

## Updating the team list

### 1. Export the latest responses

Open the HURC ESP32 Mac Address Google Sheet and download its responses as a **CSV** file. Keep the original column headers; the importer expects the response sheet's team-number, team-name, timestamp, and MAC-address columns.

Save the file somewhere convenient, such as the root of this project, and name it `responses.csv`.

### 2. Import the team information

Open this project in VS Code. Open a terminal in the project folder (the folder containing `platformio.ini`) and run:

```powershell
python scripts/import_peers_jefe.py responses.csv
```

If your CSV is somewhere else, supply its path instead:

```powershell
python scripts/import_peers_jefe.py "C:\path\to\responses.csv"
```

The script automatically updates `src/main.cpp` with the latest team names and addresses. It keeps the latest valid submission for each team, sorts the entries, and includes the debug entry. Check the terminal output to confirm the expected teams are listed.

**You do not need to manually edit the team arrays or count the entries.** When changes are made, the importer also saves a backup as `src/main.cpp.bak`.

### 3. Upload the updated firmware to El Jefe

1. Connect El Jefe to your computer with USB.
2. In VS Code, open the PlatformIO project.
3. Use **PlatformIO: Upload** (the upload arrow) to compile and upload the firmware. The configured environment is `upesy_wroom`.
4. Wait for PlatformIO to report a successful upload.

If PlatformIO cannot find the device, check the USB cable and selected serial port.

### 4. Send the update to the controllers

1. Turn on the controllers that should receive the new team list.
2. Keep them near El Jefe, with the controllers powered on throughout the update.
3. Power on or reset El Jefe. **It broadcasts the team update automatically at startup.** Uploading firmware normally restarts El Jefe, so it may already have sent the update after Step 3; resetting it sends the update again.
4. Wait for the broadcast to finish before turning off the controllers.

El Jefe sends the entire list automatically, even when it requires multiple messages. No extra configuration is needed for larger team lists.

### 5. Check the result

Open PlatformIO's **Serial Monitor** for El Jefe at **115200 baud**. After a successful transmission attempt, you should see messages similar to:

```text
Clear broadcast sent
Broadcast 6 team(s), 231 bytes
Broadcast 6 team(s), 231 bytes
Broadcast 1 team(s), 41 bytes
Update broadcast complete (receiver delivery not verified)
```

The number of messages depends on how many teams are in the list.

**Important:** A completed broadcast means El Jefe sent the messages; it does **not** guarantee that every controller received them. Check a few controllers' displayed team lists, including controllers at the edges of the area, before considering the update finished.

## If something goes wrong

| Problem | What to do |
| --- | --- |
| Import script says the CSV is missing | Check the CSV filename and path, or pass its full path in quotes. |
| Import script reports missing columns | Export the original response sheet again without renaming its column headers. |
| PlatformIO upload fails | Check USB connection, serial port, and that no other program is using the port. |
| El Jefe does not appear to send | Open Serial Monitor at 115200 baud, then reset El Jefe and watch for broadcast messages. |
| Some controllers have old or incomplete team lists | Keep all controllers powered on and nearby, then reset El Jefe to repeat the broadcast. Check the affected controllers afterward. |
| A team name or address is incorrect | Correct the response data, export a fresh CSV, and repeat the import, upload, and broadcast steps. |

## Quick checklist

- [ ] Export the newest response CSV.
- [ ] Run `python scripts/import_peers_jefe.py responses.csv`.
- [ ] Confirm the team list printed by the importer.
- [ ] Upload the project to El Jefe using PlatformIO.
- [ ] Turn on all controllers to be updated.
- [ ] Reset El Jefe and wait for its broadcast to finish.
- [ ] Verify the updated team list on the controllers.

**To resend the same list:** Leave the firmware as-is and simply reset El Jefe while the controllers are powered on. **To send a changed list:** Repeat the CSV import and firmware upload first.
