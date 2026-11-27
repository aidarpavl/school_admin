/**
 * Мектеп платформасы → Google Drive: файлдарды сақтау скрипті.
 *
 * ОРНАТУ (5 минут):
 * 1. Google Drive-та папка құрыңыз (мыс. «Мектеп платформасы»), ашып, адрестегі ID-ні көшіріңіз:
 *    https://drive.google.com/drive/folders/<ОСЫ_ID>
 * 2. https://script.google.com → «Жаңа жоба» → осы кодты түгел қойыңыз.
 * 3. Төмендегі ROOT_FOLDER_ID және SECRET мәндерін өзгертіңіз (SECRET — кез келген ұзын құпия сөз).
 * 4. «Deploy / Развернуть» → «New deployment» → түрі «Web app»:
 *      Execute as: Me (мен)        Who has access: Anyone (кез келген)
 *    → Deploy → Google рұқсаттарын беріңіз → Web app URL-ді көшіріңіз (…/exec).
 * 5. Streamlit → Settings → Secrets:
 *      GDRIVE_SCRIPT_URL = "https://script.google.com/macros/s/…/exec"
 *      GDRIVE_SECRET = "3-қадамдағы SECRET"
 * Файлды тек SECRET білетін бағдарлама ғана жаза алады.
 */
const ROOT_FOLDER_ID = 'ОСЫНДА_ПАПКА_ID';
const SECRET = 'ОСЫНДА_ҰЗЫН_ҚҰПИЯ_СӨЗ';

function doPost(e) {
  try {
    const d = JSON.parse(e.postData.contents);
    if (d.secret !== SECRET) return out_({ ok: false, error: 'secret қате' });
    let folder = DriveApp.getFolderById(ROOT_FOLDER_ID);
    (d.path || '').split('/').filter(String).forEach(function (name) {
      const it = folder.getFoldersByName(name);
      folder = it.hasNext() ? it.next() : folder.createFolder(name);
    });
    const blob = Utilities.newBlob(Utilities.base64Decode(d.data), d.mime, d.name);
    const old = folder.getFilesByName(d.name);           // аттас файл болса — жаңа нұсқамен ауыстыру
    while (old.hasNext()) old.next().setTrashed(true);
    const f = folder.createFile(blob);
    return out_({ ok: true, id: f.getId(), url: f.getUrl() });
  } catch (err) {
    return out_({ ok: false, error: String(err) });
  }
}

function doGet() {
  return out_({ ok: true, info: 'Мектеп платформасы Drive скрипті жұмыс істеп тұр' });
}

function out_(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}
