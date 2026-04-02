#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { createRequire } = require('module');

function parseArgs(argv) {
  const args = {
    apply: false,
    names: ['openAI', 'anthropic'],
  };

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--apply') {
      args.apply = true;
      continue;
    }
    if (arg.startsWith('--user-id=')) {
      args.userId = arg.slice('--user-id='.length);
      continue;
    }
    if (arg === '--user-id') {
      args.userId = argv[++i];
      continue;
    }
    if (arg.startsWith('--old-env=')) {
      args.oldEnv = arg.slice('--old-env='.length);
      continue;
    }
    if (arg === '--old-env') {
      args.oldEnv = argv[++i];
      continue;
    }
    if (arg.startsWith('--new-env=')) {
      args.newEnv = arg.slice('--new-env='.length);
      continue;
    }
    if (arg === '--new-env') {
      args.newEnv = argv[++i];
      continue;
    }
    if (arg.startsWith('--backup-dir=')) {
      args.backupDir = arg.slice('--backup-dir='.length);
      continue;
    }
    if (arg === '--backup-dir') {
      args.backupDir = argv[++i];
      continue;
    }
    if (arg.startsWith('--names=')) {
      args.names = arg
        .slice('--names='.length)
        .split(',')
        .map((value) => value.trim())
        .filter(Boolean);
      continue;
    }
    if (arg === '--names') {
      args.names = (argv[++i] ?? '')
        .split(',')
        .map((value) => value.trim())
        .filter(Boolean);
      continue;
    }
    if (arg === '--help' || arg === '-h') {
      args.help = true;
      continue;
    }
    throw new Error(`Unknown argument: ${arg}`);
  }

  return args;
}

function usage() {
  console.log(`Usage:
  node scripts/viventium/migrate_connected_account_keys.js \\
    --user-id <mongo-user-id> \\
    --old-env <private-librechat-env> \\
    --new-env <live-librechat-env> \\
    --backup-dir <private-backup-dir> \\
    [--names openAI,anthropic] \\
    [--apply]

Default mode is dry-run. Pass --apply to persist the migrated values.
`);
}

function readEnvFile(dotenv, filePath) {
  const absolutePath = path.resolve(filePath);
  if (!fs.existsSync(absolutePath)) {
    throw new Error(`Env file not found: ${absolutePath}`);
  }
  return dotenv.parse(fs.readFileSync(absolutePath));
}

function createCryptoHelpers(env) {
  const keyHex = env.CREDS_KEY;
  const ivHex = env.CREDS_IV;
  if (!keyHex || !ivHex) {
    throw new Error('Missing CREDS_KEY or CREDS_IV in env file');
  }
  const key = Buffer.from(keyHex, 'hex');
  const iv = Buffer.from(ivHex, 'hex');

  if (key.length !== 32) {
    throw new Error(`Invalid CREDS_KEY length: expected 32 bytes, got ${key.length}`);
  }
  if (iv.length !== 16) {
    throw new Error(`Invalid CREDS_IV length: expected 16 bytes, got ${iv.length}`);
  }

  return {
    decrypt(value) {
      if (value.startsWith('v3:')) {
        const [, ivPart, encryptedPart] = value.split(':');
        const decipher = crypto.createDecipheriv(
          'aes-256-ctr',
          key,
          Buffer.from(ivPart, 'hex'),
        );
        const decrypted = Buffer.concat([
          decipher.update(Buffer.from(encryptedPart, 'hex')),
          decipher.final(),
        ]);
        return decrypted.toString('utf8');
      }

      if (value.includes(':')) {
        const [ivPart, encryptedPart] = value.split(/:(.*)/s).filter(Boolean);
        const decipher = crypto.createDecipheriv(
          'aes-256-cbc',
          key,
          Buffer.from(ivPart, 'hex'),
        );
        const decrypted = Buffer.concat([
          decipher.update(Buffer.from(encryptedPart, 'hex')),
          decipher.final(),
        ]);
        return decrypted.toString('utf8');
      }

      const decipher = crypto.createDecipheriv('aes-256-cbc', key, iv);
      const decrypted = Buffer.concat([
        decipher.update(Buffer.from(value, 'hex')),
        decipher.final(),
      ]);
      return decrypted.toString('utf8');
    },
    encryptLegacy(value) {
      const cipher = crypto.createCipheriv('aes-256-cbc', key, iv);
      const encrypted = Buffer.concat([cipher.update(value, 'utf8'), cipher.final()]);
      return encrypted.toString('hex');
    },
  };
}

function shouldPersistWithoutExpiry(plaintextValue) {
  try {
    const parsed = JSON.parse(plaintextValue);
    return parsed?.oauthType === 'subscription';
  } catch {
    return false;
  }
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    usage();
    return;
  }
  if (!args.userId || !args.oldEnv || !args.newEnv || !args.backupDir) {
    usage();
    process.exitCode = 1;
    return;
  }

  const repoRoot = path.resolve(__dirname, '..', '..');
  const librechatRoot = path.join(repoRoot, 'viventium_v0_4', 'LibreChat');
  const lcRequire = createRequire(path.join(librechatRoot, 'package.json'));
  const dotenv = lcRequire('dotenv');
  const { MongoClient, ObjectId } = lcRequire('mongodb');

  const oldEnv = readEnvFile(dotenv, args.oldEnv);
  const newEnv = readEnvFile(dotenv, args.newEnv);
  const mongoUri = newEnv.MONGO_URI || process.env.MONGO_URI;
  if (!mongoUri) {
    throw new Error('Missing MONGO_URI in new env file and process environment');
  }

  const oldCrypto = createCryptoHelpers(oldEnv);
  const newCrypto = createCryptoHelpers(newEnv);

  const backupDir = path.resolve(args.backupDir);
  fs.mkdirSync(backupDir, { recursive: true });
  const timestamp = new Date().toISOString().replace(/[-:]/g, '').replace(/\.\d+Z$/, 'Z');
  const backupPath = path.join(
    backupDir,
    `connected-account-key-migration-${args.userId}-${timestamp}.json`,
  );

  const client = new MongoClient(mongoUri);
  await client.connect();
  try {
    const dbName = new URL(mongoUri).pathname.replace(/^\//, '') || 'LibreChat';
    const db = client.db(dbName);
    const userObjectId = new ObjectId(args.userId);
    const docs = await db
      .collection('keys')
      .find({ userId: userObjectId, name: { $in: args.names } })
      .toArray();

    if (docs.length === 0) {
      throw new Error(`No key documents found for user ${args.userId} and names ${args.names.join(', ')}`);
    }

    const report = {
      createdAt: new Date().toISOString(),
      apply: args.apply,
      userId: args.userId,
      names: args.names,
      mongoUriRedacted: mongoUri.replace(/\/\/.*@/, '//***:***@'),
      docs: docs.map((doc) => ({
        _id: String(doc._id),
        userId: String(doc.userId),
        name: doc.name,
        __v: doc.__v,
        expiresAt: doc.expiresAt ?? null,
        value: doc.value,
      })),
      migrated: [],
    };

    for (const doc of docs) {
      const plaintext = oldCrypto.decrypt(doc.value);
      const reEncryptedValue = newCrypto.encryptLegacy(plaintext);
      const verifiedPlaintext = newCrypto.decrypt(reEncryptedValue);
      if (verifiedPlaintext !== plaintext) {
        throw new Error(`Verification failed for ${doc.name}`);
      }

      const persistWithoutExpiry = shouldPersistWithoutExpiry(plaintext);
      report.migrated.push({
        _id: String(doc._id),
        name: doc.name,
        expiresAtBefore: doc.expiresAt ?? null,
        expiresAtAfter: persistWithoutExpiry ? null : doc.expiresAt ?? null,
        plaintextPreview: plaintext.slice(0, 120),
      });

      if (!args.apply) {
        continue;
      }

      const update = {
        $set: {
          value: reEncryptedValue,
        },
      };
      if (persistWithoutExpiry) {
        update.$unset = { expiresAt: '' };
      } else if (doc.expiresAt) {
        update.$set.expiresAt = doc.expiresAt;
      } else {
        update.$unset = { expiresAt: '' };
      }

      await db.collection('keys').updateOne({ _id: doc._id }, update);
    }

    fs.writeFileSync(backupPath, JSON.stringify(report, null, 2));
    console.log(
      JSON.stringify(
        {
          ok: true,
          apply: args.apply,
          backupPath,
          migratedCount: report.migrated.length,
          migrated: report.migrated.map((entry) => ({
            name: entry.name,
            expiresAtAfter: entry.expiresAtAfter,
          })),
        },
        null,
        2,
      ),
    );
  } finally {
    await client.close();
  }
}

main().catch((error) => {
  console.error(error.stack || String(error));
  process.exit(1);
});
