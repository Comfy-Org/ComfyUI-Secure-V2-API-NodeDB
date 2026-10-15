$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
$taskOut = Join-Path $taskRoot 'evidence/run1'
if (Test-Path -LiteralPath $taskOut) { throw 'Preserve prior run; use a new evidence path.' }
New-Item -ItemType Directory -Path $taskOut | Out-Null
$taskInputs = @(Get-ChildItem -LiteralPath (Join-Path $taskRoot 'candidate') -File -Recurse)
$taskInputs += @(Get-ChildItem -LiteralPath $taskRoot -File)
$taskHashes = @{}
foreach ($taskFile in $taskInputs) { $taskHashes[$taskFile.FullName.Substring($taskRoot.Length + 1)] = (Get-FileHash -LiteralPath $taskFile.FullName -Algorithm SHA256).Hash.ToLower() }
$taskArgs = @('--max-old-space-size=512', '--experimental-vm-modules', ('"' + (Join-Path $taskRoot 'run-all.mjs') + '"'))
$taskWatch = [System.Diagnostics.Stopwatch]::StartNew()
$taskProcess = Start-Process -FilePath 'C:\Program Files\nodejs\node.exe' -ArgumentList $taskArgs -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $taskOut 'stdout.txt') -RedirectStandardError (Join-Path $taskOut 'stderr.txt')
$taskHandle = $taskProcess.Handle
try { $taskProcess.ProcessorAffinity = [IntPtr]1 } catch { if (!$taskProcess.HasExited) { throw } }
$taskTimeout = !$taskProcess.WaitForExit(90000)
if ($taskTimeout) { $taskProcess.Kill(); $taskProcess.WaitForExit() }
$taskProcess.Refresh()
$taskCode = if ($taskTimeout) { 124 } else { $taskProcess.ExitCode }
$taskReceipt = @{status=$(if ($taskCode -eq 0) {'PASS'} else {'FAIL'}); exit_code=$taskCode; wall_seconds=$taskWatch.Elapsed.TotalSeconds; limits=@{cpus=1; v8_heap_mib=512; wall_seconds=90; dependency_install=$false}; source_sha256=$taskHashes; command=@('node','--max-old-space-size=512','--experimental-vm-modules','lifecycle-r2/run-all.mjs')}
$taskReceipt | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $taskOut 'receipt.json') -Encoding utf8
Write-Output ([pscustomobject]$taskReceipt | Select-Object status,exit_code,wall_seconds,limits | ConvertTo-Json -Compress)
Get-Content -LiteralPath (Join-Path $taskOut 'stdout.txt') -Tail 16
if ($taskCode -ne 0) { Get-Content -LiteralPath (Join-Path $taskOut 'stderr.txt') -Tail 55 }
exit $taskCode
