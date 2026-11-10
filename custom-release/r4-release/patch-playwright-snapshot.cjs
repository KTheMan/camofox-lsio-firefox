// Patch the pinned serializer before any browser is launched. Unknown bundles
// fail closed rather than falling back to value-bearing accessibility output.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const root = process.argv[2] || path.dirname(require.resolve('playwright-core/package.json'));
const bundle = path.join(root, 'lib/coreBundle.js');
const pkg = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8'));
if (pkg.version !== '1.62.1') throw new Error('Snapshot privacy patch requires pinned playwright-core 1.62.1');
let source = fs.readFileSync(bundle, 'utf8');
const marker = 'CAMOFOX_SNAPSHOT_PRIVACY_V2';
const policy = require('../lib/sensitive-fields-policy.json');
if (source.includes(marker)) {
  process.stdout.write('Snapshot privacy patch already installed\n');
  process.exit(0);
}
const expected = '9393fa79e1c67c74edc26b610d65a4f7ed73d345a762465cc88340a33a2454ac';
if (crypto.createHash('sha256').update(source).digest('hex') !== expected)
  throw new Error('Unexpected Playwright serializer digest; refusing an unverified privacy patch');
function replaceOnce(before, after, count = 1) {
  // The injected script is stored as an escaped JavaScript string in the bundle.
  const encoded = (value) => value.replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/\r/g, '\\r').replace(/\n/g, '\\n');
  const needle = encoded(before);
  if (source.split(needle).length !== count + 1) throw new Error('Snapshot serializer anchor changed');
  source = source.split(needle).join(encoded(after));
}
const helper = `function camofoxSensitiveControl(element) {
  // ${marker}: never change the actual DOM value, selection or input events.
  const formControl = element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement || element instanceof HTMLSelectElement || element.isContentEditable;
  if (!formControl) return false;
  return element.type === "password" || new RegExp(${JSON.stringify(policy.pattern)}, "i").test([element.id, element.name, element.autocomplete, element.getAttribute("autocomplete"), element.getAttribute("aria-label")].join(" "));
}
`;
replaceOnce('function toAriaNode(element, options, nameSourceElements) {', helper + 'function toAriaNode(element, options, nameSourceElements) {');
replaceOnce('result.children = [element.value];', 'result.children = [camofoxSensitiveControl(element) ? "[redacted]" : element.value];');
replaceOnce('return compositeString(element.value, element, options.collectElements);', 'return compositeString(camofoxSensitiveControl(element) ? "[redacted]" : element.value, element, options.collectElements);', 2);
replaceOnce('if (!isOwnLabel && !isOwnLabelledBy) {\n      if (role === "textbox") {',
  'if (!isOwnLabel && !isOwnLabelledBy) {\n      if (camofoxSensitiveControl(element)) return compositeString("[redacted]", element, options.collectElements);\n      if (role === "textbox") {');
replaceOnce('processElement(childAriaNode || ariaNode, element, ariaChildren, visible);',
  'if (camofoxSensitiveControl(element)) { if (childAriaNode) childAriaNode.children = ["[redacted]"]; } else processElement(childAriaNode || ariaNode, element, ariaChildren, visible);');
fs.writeFileSync(bundle, source);
process.stdout.write('Installed pinned snapshot privacy patch\n');
