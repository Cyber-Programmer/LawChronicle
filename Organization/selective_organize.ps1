# Selective File Organization Script
# Applies unified naming convention only where needed
# Preserves good existing naming and focuses on problematic files

param(
    [switch]$DryRun = $false,
    [string]$LogFile = "selective_organization_$(Get-Date -Format 'yyyy-MM-dd_HHmmss').csv"
)

# Initialize log
$logData = @()
$successCount = 0
$skippedCount = 0
$errorCount = 0

function Write-Log {
    param($Message, $Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] [$Level] $Message" -ForegroundColor $(
        switch($Level) {
            "ERROR" { "Red" }
            "WARNING" { "Yellow" }
            "SUCCESS" { "Green" }
            default { "White" }
        }
    )
}

function Test-GoodNaming {
    param([string]$FileName)
    
    # Files that already follow good patterns
    if ($FileName -match "^[a-z]+-[a-z0-9-]+\.(py|json|md)$") { return $true }
    if ($FileName -match "^(doc|config|comparison|merge|export|cleaning|test)-.*\.(py|json|md)$") { return $true }
    if ($FileName -like "phase*.md" -or $FileName -like "README*" -or $FileName -like "requirements*") { return $true }
    
    return $false
}

function Get-SelectiveStandardizedName {
    param(
        [string]$OriginalName,
        [string]$FilePath
    )
    
    $ext = [System.IO.Path]::GetExtension($OriginalName)
    $baseName = [System.IO.Path]::GetFileNameWithoutExtension($OriginalName)
    
    # Documentation files with dates at start
    if ($OriginalName -match "^(\d{4}-\d{2}-\d{2})-(.*)\.(md)$") {
        $date = $matches[1]
        $content = $matches[2] -replace "_", "-"
        if ($content -like "*audit*") { return "doc-audit-$date$ext" }
        if ($content -like "*summary*" -or $content -like "*implementation*") { return "doc-summary-$date$ext" }
        return "doc-$content-$date$ext"
    }
    
    # Config files that need underscores converted
    if ($OriginalName -match "^config_(.+)\.json$") {
        $configType = $matches[1] -replace "_", "-"
        return "config-$configType$ext"
    }
    
    # Test files that need modernization (but keep them as test files)
    if ($OriginalName -match "^test_(.+)\.py$") {
        $testType = $matches[1] -replace "_", "-"
        return "test-$testType$ext"
    }
    
    # Tool files that need modernization
    if ($FilePath -like "*tools*" -and $OriginalName -match "^(.+)\.py$") {
        $toolName = $matches[1] -replace "_", "-"
        return "tool-$toolName$ext"
    }
    
    # Files with underscores that should be hyphens
    if ($OriginalName -match "_" -and -not (Test-GoodNaming $OriginalName)) {
        return $OriginalName -replace "_", "-"
    }
    
    return $null  # No change needed
}

function Rename-FileSelectively {
    param(
        [string]$FilePath,
        [string]$NewName
    )
    
    $originalFile = Get-Item $FilePath
    $directory = $originalFile.Directory.FullName
    $newPath = Join-Path $directory $NewName
    
    $logEntry = [PSCustomObject]@{
        OriginalPath = $FilePath
        OriginalName = $originalFile.Name
        NewName = $NewName
        NewPath = $newPath
        Directory = $directory
        Status = ""
        Error = ""
        Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        Reason = ""
    }
    
    try {
        if ($originalFile.Name -eq $NewName) {
            $logEntry.Status = "SKIPPED_SAME_NAME"
            $logEntry.Reason = "No change needed"
            $script:skippedCount++
            Write-Log "Skipped (same name): $($originalFile.Name)" "WARNING"
        }
        elseif (Test-Path $newPath) {
            $logEntry.Status = "SKIPPED_EXISTS"
            $logEntry.Error = "Target file already exists"
            $logEntry.Reason = "Target exists"
            $script:skippedCount++
            Write-Log "Skipped (exists): $($originalFile.Name) -> $NewName" "WARNING"
        }
        elseif ($DryRun) {
            $logEntry.Status = "DRY_RUN"
            $logEntry.Reason = "Would rename"
            $script:successCount++
            Write-Log "DRY RUN: $($originalFile.Name) -> $NewName" "INFO"
        }
        else {
            Rename-Item -Path $FilePath -NewName $NewName -Force
            $logEntry.Status = "SUCCESS"
            $logEntry.Reason = "Renamed successfully"
            $script:successCount++
            Write-Log "Renamed: $($originalFile.Name) -> $NewName" "SUCCESS"
        }
    }
    catch {
        $logEntry.Status = "ERROR"
        $logEntry.Error = $_.Exception.Message
        $logEntry.Reason = "Rename failed"
        $script:errorCount++
        Write-Log "Error renaming $($originalFile.Name): $($_.Exception.Message)" "ERROR"
    }
    
    return $logEntry
}

Write-Log "Starting selective file organization" "INFO"
Write-Log "Mode: $(if($DryRun){'DRY RUN'}else{'ACTUAL RENAME'})" "INFO"

# Get all relevant files for selective processing
$allFiles = Get-ChildItem -Path "." -Recurse -File | Where-Object { 
    # Skip already perfectly named files
    -not (Test-GoodNaming $_.Name) -and
    # Focus on files that need attention
    (
        $_.Name -like "test_*.py" -or
        $_.Name -like "config_*.json" -or
        $_.Name -match "^\d{4}-\d{2}-\d{2}-.*\.md$" -or
        ($_.Directory.Name -eq "tools" -and $_.Extension -eq ".py") -or
        ($_.Name -match "_" -and $_.Extension -in @(".py", ".json", ".md"))
    ) -and
    # Skip cache and build files
    $_.FullName -notlike "*__pycache__*" -and
    $_.FullName -notlike "*node_modules*" -and
    $_.FullName -notlike "*build*"
}

Write-Log "Found $($allFiles.Count) files that may need renaming" "INFO"

foreach ($file in $allFiles) {
    $newName = Get-SelectiveStandardizedName -OriginalName $file.Name -FilePath $file.FullName
    
    if ($newName -and $newName -ne $file.Name) {
        $logData += Rename-FileSelectively -FilePath $file.FullName -NewName $newName
    } else {
        Write-Log "Skipped (good naming): $($file.Name)" "INFO"
        $logData += [PSCustomObject]@{
            OriginalPath = $file.FullName
            OriginalName = $file.Name
            NewName = $file.Name
            NewPath = $file.FullName
            Directory = $file.Directory.FullName
            Status = "SKIPPED_GOOD_NAMING"
            Error = ""
            Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
            Reason = "Already follows good naming convention"
        }
        $skippedCount++
    }
}

# Export log
Write-Log "Exporting log to $LogFile..." "INFO"
$logData | Export-Csv -Path $LogFile -NoTypeInformation

# Summary
Write-Log "Selective file organization completed!" "SUCCESS"
Write-Log "Total files processed: $($logData.Count)" "INFO"
Write-Log "Successfully renamed: $successCount" "SUCCESS"
Write-Log "Skipped: $skippedCount" "WARNING"
Write-Log "Errors: $errorCount" "ERROR"

if ($DryRun) {
    Write-Log "This was a DRY RUN. To apply changes, run without -DryRun flag" "INFO"
}

# Show summary of what would be renamed
if ($DryRun -and $successCount -gt 0) {
    Write-Log "`nFiles that would be renamed:" "INFO"
    $logData | Where-Object { $_.Status -eq "DRY_RUN" } | ForEach-Object {
        Write-Host "  $($_.OriginalName) -> $($_.NewName)" -ForegroundColor Cyan
    }
}

return $logData
