$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath('E:\zhoumian\FPGA\FPGA_GS\FPGA_GSV1').TrimEnd('\')
$manifestPath = Join-Path $PSScriptRoot 'verified_manifest.json'
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ([IO.Path]::GetFullPath($manifest.root).TrimEnd('\') -ne $root) { throw 'Unexpected manifest root' }
if ($manifest.status -ne 'archive_verified_ready_for_removal') { throw 'Archive not verified' }
if ((Get-FileHash -LiteralPath $manifest.archive -Algorithm SHA256).Hash -ne $manifest.archive_sha256) { throw 'Archive SHA mismatch' }
if ((Get-FileHash -LiteralPath $manifest.wip_archive -Algorithm SHA256).Hash -ne $manifest.wip_archive_sha256) { throw 'WIP archive SHA mismatch' }
$buildPrefix = (Join-Path $root 'build') + '\'
$wip = Join-Path $root 'deliverables\FPGA_GSV1_M3_05_3_4_WIP_NO_BIT_20261021_104224'
if ([IO.Path]::GetFullPath($manifest.wip_directory) -ne $wip) { throw 'Unexpected WIP target' }
$wipPrefix = $wip + '\'
$all = @($manifest.files) + @($manifest.wip_files)
# Validate every absolute target, category and SHA before removing the first file.
foreach ($entry in $all) {
    $path = [IO.Path]::GetFullPath($entry.path)
    if (!$path.StartsWith($root + '\', [StringComparison]::OrdinalIgnoreCase)) { throw "Outside project: $path" }
    $generated = $path.StartsWith($buildPrefix, [StringComparison]::OrdinalIgnoreCase)
    $duplicate = $path.StartsWith($wipPrefix, [StringComparison]::OrdinalIgnoreCase)
    if (!$generated -and !$duplicate) { throw "Unexpected cleanup category: $path" }
    if ($generated) {
        $relative = $path.Substring($buildPrefix.Length)
        if ($relative -notmatch '^(?:M1_\d+|M2_\d+|M3_(?:01|02|03|05))_[^\\]+\\(?:compile|device_map|place_route|report_timing|synthesize|generate_bitstream)\\') { throw "Unexpected historical build path: $path" }
        if ([IO.Path]::GetExtension($path) -notin @('.db', '.adf', '.vm', '.netlist')) { throw 'Unexpected file suffix' }
    }
    $item = Get-Item -LiteralPath $path -Force
    if ($item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Not a regular file' }
    if ($item.Length -ne $entry.bytes -or (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $entry.sha256) { throw "Changed since archive: $path" }
}
if (@(Get-ChildItem -LiteralPath $wip -Recurse -File -Force).Count -ne @($manifest.wip_files).Count) { throw 'WIP file count changed' }
$removed = [Collections.Generic.List[string]]::new()
$bytes = [int64]0
try {
    foreach ($entry in $all) {
        Remove-Item -LiteralPath $entry.path -Force
        $removed.Add($entry.path)
        $bytes += $entry.bytes
    }
    # Only remove confirmed empty directories inside the exact duplicate WIP target.
    foreach ($dir in @(Get-ChildItem -LiteralPath $wip -Directory -Recurse -Force | Sort-Object { $_.FullName.Length } -Descending)) {
        $target = [IO.Path]::GetFullPath($dir.FullName)
        if (!$target.StartsWith($wipPrefix, [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe directory target' }
        if (!(Get-ChildItem -LiteralPath $target -Force | Select-Object -First 1)) { Remove-Item -LiteralPath $target -Force }
    }
    if (!(Get-ChildItem -LiteralPath $wip -Force | Select-Object -First 1)) { Remove-Item -LiteralPath $wip -Force }
    $status = 'originals_removed_archive_preserved'
} finally {
    $result = [ordered]@{status=$status; removed_files=$removed.Count; original_bytes_removed=$bytes; archive_bytes=$manifest.archive_bytes; net_bytes_reclaimed=($bytes-$manifest.archive_bytes); archive=$manifest.archive; archive_sha256=$manifest.archive_sha256; removed_paths=@($removed.ToArray()); scope=$manifest.scope}
    $result | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'removal_result.json') -Encoding UTF8
}
[pscustomobject]$result | Select-Object status,removed_files,original_bytes_removed,archive_bytes,net_bytes_reclaimed | ConvertTo-Json
