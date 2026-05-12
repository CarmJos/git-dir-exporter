# Command Examples

## 1) Dry-run with full history

```powershell
python .\src\run.py `
  --source-repo "D:\@DEV\monorepo" `
  --source-subdir "services/payment" `
  --target-dir "D:\@DEV\payment-standalone" `
  --rev-range "HEAD" `
  --dry-run
```

## 2) Export a bounded revision range

```powershell
python .\src\run.py `
  --source-repo "D:\@DEV\monorepo" `
  --source-subdir "services/payment" `
  --target-dir "D:\@DEV\payment-standalone" `
  --rev-range "a1b2c3d^..f6e5d4c" `
  --force-clean-target
```

## 3) Replay only first 30 matched commits

```powershell
python .\src\run.py `
  --source-repo "D:\@DEV\monorepo" `
  --source-subdir "services/payment" `
  --target-dir "D:\@DEV\payment-standalone" `
  --rev-range "HEAD" `
  --limit 30 `
  --force-clean-target
```

## Verify Result

```powershell
git -C "D:\@DEV\payment-standalone" --no-pager log --oneline --decorate -n 20
git -C "D:\@DEV\payment-standalone" status
```

