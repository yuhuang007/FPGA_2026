param([ValidateSet('Start','Stop')][string]$Action='Start',[switch]$NoPause,[switch]$NoBrowser,[ValidateSet('LIVE_FRONT','FILE_TEST')][string]$Mode='LIVE_FRONT')
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false);$OutputEncoding=[Console]::OutputEncoding
$state=Join-Path $PSScriptRoot 'state';New-Item -ItemType Directory -Force $state|Out-Null
$report=[ordered]@{version='M4-07-r1-netrx-ready';action=$Action;ok=$false};$lock=$null
function Save($o,$p){[IO.File]::WriteAllText($p,($o|ConvertTo-Json -Depth 35),[Text.UTF8Encoding]::new($false))}
function OwnedTunnel {
 $file=Join-Path $state 'candidate_tunnel.json';if(!(Test-Path $file)){return $null}
 $r=Get-Content $file -Raw -Encoding UTF8|ConvertFrom-Json
 $p=Get-CimInstance Win32_Process -Filter "ProcessId=$($r.pid)" -ErrorAction SilentlyContinue
 if($p -and $p.Name -eq 'ssh.exe' -and $p.CommandLine -eq $r.command_line -and [string]$p.CreationDate -eq $r.creation_date){return $p};return $null
}
try {
 $lock=[IO.File]::Open((Join-Path $state 'candidate_operation.lock'),[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
 $cfg=Get-Content (Join-Path (Split-Path $PSScriptRoot -Parent) 'oneclick/config.json') -Raw -Encoding UTF8|ConvertFrom-Json
 if($cfg.remote_dir -notmatch '^/[A-Za-z0-9_./-]+$' -or $cfg.ssh_host -notmatch '^[A-Za-z0-9._:-]+$' -or $cfg.ssh_user -notmatch '^[A-Za-z0-9_-]+$'){throw '集中配置SSH地址/用户名/路径无效'}
 $ssh=(Get-Command ssh.exe).Source;$target="$($cfg.ssh_user)@$($cfg.ssh_host)"
 $sshArgs=@('-p',"$($cfg.ssh_port)",'-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=8','-o','ServerAliveInterval=10','-o','ServerAliveCountMax=3')
 $listeners=@(Get-NetTCPConnection -LocalPort 18084 -State Listen -ErrorAction SilentlyContinue)
 $own=OwnedTunnel
 if($Action -eq 'Start'){
  foreach($l in $listeners){if(!$own -or $l.OwningProcess -ne $own.ProcessId){
   $p=Get-CimInstance Win32_Process -Filter "ProcessId=$($l.OwningProcess)"
   throw "18084被其他/未确认进程占用：PID=$($p.ProcessId) $($p.CommandLine)，未结束它。"
  }}
  if($own -and $own.CommandLine -notmatch ([regex]::Escape($target)+'(?:\s|$)')){throw '候选旧地址转发仍在；先双击候选停止入口，未擅自接管。'}
 }
 if($Action -eq 'Start'){
  $configCopy=Join-Path $state 'ops_config.json';Save $cfg $configCopy
  & scp.exe -P $cfg.ssh_port -o StrictHostKeyChecking=yes $configCopy "${target}:$($cfg.remote_dir)/m407/ops_config.json"
  if($LASTEXITCODE -ne 0){throw '集中配置同步失败'}
 }
 Write-Host "独立候选：$target，远端8084 → 本机18084。默认8080/18080入口不修改。"
 $reply=Join-Path $state 'candidate_reply.json'
 & $ssh @sshArgs $target "cd '$($cfg.remote_dir)' && .venv/bin/python m407/ops.py $($Action.ToLower()) --mode $Mode" > $reply
 if($LASTEXITCODE -ne 0){throw 'SSH/认证/主机校验或远端入口失败；密码只在终端输入，不保存。'}
 $remote=Get-Content $reply -Raw -Encoding UTF8|ConvertFrom-Json;$report.remote=$remote
 Write-Host $remote.message
 if(!$remote.ok){throw ($remote|ConvertTo-Json -Depth 6)}
 if($Action -eq 'Stop'){
  if($own){Stop-Process -Id $own.ProcessId;Write-Host '已关闭本候选入口创建且身份一致的SSH转发。'}
 }else{
  if(!$listeners.Count){
   & $ssh @sshArgs '-o' 'BatchMode=yes' $target 'true' 2>$null
   $style=if($LASTEXITCODE -eq 0){'Hidden'}else{'Normal'}
   if($style -eq 'Normal'){Write-Host '请在弹出的SSH转发终端输入密码。关闭它会断开预览，远端候选继续运行。'}
   $child=Start-Process $ssh -ArgumentList ($sshArgs+@('-N','-o','ExitOnForwardFailure=yes','-L','127.0.0.1:18084:127.0.0.1:8084',$target)) -WindowStyle $style -PassThru
   $end=[DateTime]::UtcNow.AddSeconds(4)
   do{$p=Get-CimInstance Win32_Process -Filter "ProcessId=$($child.Id)" -ErrorAction SilentlyContinue;if($p.CommandLine){break};Start-Sleep -Milliseconds 100}while([DateTime]::UtcNow -lt $end)
   if(!$p.CommandLine){throw '转发PID身份未就绪，未猜测接管'}
   Save @{pid=$p.ProcessId;command_line=$p.CommandLine;creation_date=[string]$p.CreationDate} (Join-Path $state 'candidate_tunnel.json')
  }
  $end=[DateTime]::UtcNow.AddSeconds(45);$http=$null
  do{
   try{$http=Invoke-RestMethod 'http://127.0.0.1:18084/status.json' -TimeoutSec 2}catch{$http=$null}
   if($http -and $http.instance -eq $remote.status.instance){break};Start-Sleep -Milliseconds 200
  }while([DateTime]::UtcNow -lt $end)
  if(!$http -or $http.instance -ne $remote.status.instance){throw 'HTTP/转发身份核对超时；远端可能继续运行，请用候选停止入口。'}
  Write-Host "候选已就绪，PID=$($remote.process.pid)，http://127.0.0.1:18084/"
  Write-Host 'LIVE_FRONT：实时前摄／FPGA网口1输入。新固件来源待核对；旧上传不算NET_RX验收。控制关系未知，不自动放行。'
  Write-Host '关闭本窗口后远端继续运行。停止用同目录“停止M407候选.cmd”。回退用同目录“回退原前摄.cmd”，恢复旧LIVE入口。'
  if(!$NoBrowser){Start-Process 'http://127.0.0.1:18084/'}
 }
 $report.ok=$true
}catch{$report.error=$_.Exception.Message;Write-Host ('未完成：'+$report.error) -ForegroundColor Red}
finally{
 if($lock){$lock.Dispose()};Save $report (Join-Path $state ("candidate_$($Action.ToLower())_$(Get-Date -Format yyyyMMdd_HHmmss_fff).json"))
 if(!$NoPause){Read-Host '按回车关闭'|Out-Null}
}
if(!$report.ok){exit 1}
