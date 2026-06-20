const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const extPath = path.join(root, "extensions/vscode-meris/extension.js");
const idxPath = path.join(root, "meris/ui/static/index.html");

const ext = fs.readFileSync(extPath, "utf8");
const idx = fs.readFileSync(idxPath, "utf8");
let body = idx.match(/<body>([\s\S]*)<\/body>/)[1].trim();

body = body
  .replace(
    '<script src="/media/agent.js"></script>',
    '<script nonce="${nonce}" src="${scriptUri}"></script>'
  )
  .replace(
    '<script src="/media/phase-i.js"></script>',
    '<script nonce="${nonce}" src="${phaseIUri}"></script>'
  )
  .replace(
    '<script src="/media/harness-ui.js"></script>',
    '<script nonce="${nonce}" src="${harnessUiUri}"></script>'
  )
  .replace(
    '<script src="/media/settings-ui.js"></script>',
    '<script nonce="${nonce}" src="${settingsUiUri}"></script>'
  )
  .replace(
    '<script src="/media/composer-media.js"></script>',
    '<script nonce="${nonce}" src="${composerMediaUri}"></script>'
  );

const start = ext.indexOf("<body>");
const endMarker = "</html>`";
const end = ext.indexOf(endMarker, start);
if (start < 0 || end < 0) {
  throw new Error("markers not found");
}

const out = ext.slice(0, start) + "<body>\n" + body + "\n</html>`" + ext.slice(end + endMarker.length);
fs.writeFileSync(extPath, out);
console.log("synced extension.js body", body.length, "chars");
