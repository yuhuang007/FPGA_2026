param([Parameter(Mandatory=$true)][string]$Port,[int]$Seconds=15,[string]$Output='net2_diag.txt')
$ErrorActionPreference='Stop'
# Built-in .NET SerialPort only. No driver installation or network changes.
$serial=[IO.Ports.SerialPort]::new($Port,115200,[IO.Ports.Parity]::None,8,[IO.Ports.StopBits]::One)
$serial.Handshake=[IO.Ports.Handshake]::None
$serial.DtrEnable=$false;$serial.RtsEnable=$false;$serial.ReadTimeout=1200
$lines=[Collections.Generic.List[string]]::new();$lastBlcPhase=-1
try {
 $serial.Open();$until=[DateTime]::UtcNow.AddSeconds($Seconds)
 while([DateTime]::UtcNow -lt $until){
  try {$line=$serial.ReadLine().Trim();if($line -match '^N2 35[OPIB] '){$lines.Add($line);Write-Output $line
    if($line -match '^N2 35B '){
      $words=$line.Split(' ',[StringSplitOptions]::RemoveEmptyEntries)
      if($words.Length -eq 42 -and $words[22] -eq '43314254'){
        $phase=([Convert]::ToUInt32($words[23],16) -shr 29)
        if($phase -ne $lastBlcPhase){
          $names=@('COVER/PREP: keep lens covered','A: fixed exposure/gain/WB, BLC update','B: BLC frozen','Aprime: original BLC update restored','DONE: operating controls restored, uncover lens','INVALID: see error/readback; do not judge BLC effect')
          Write-Host ('E5 BLC '+$names[[Math]::Min($phase,5)])
          $lastBlcPhase=$phase
        }
      }
    }}}
  catch [TimeoutException] {}
 }
} finally {if($serial.IsOpen){$serial.Close()};$serial.Dispose()}
if($lines.Count -eq 0){throw 'No N2 35O/35P/35I/35B line. Check the selected board CP2102 COM port and USB UART cable; do not change Ethernet settings.'}
[IO.File]::WriteAllLines([IO.Path]::GetFullPath($Output),$lines,[Text.Encoding]::ASCII)
Write-Output "Saved $($lines.Count) lines to $([IO.Path]::GetFullPath($Output))"

