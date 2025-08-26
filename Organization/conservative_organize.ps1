# Conservative File Organization Script
# Only renames files that are safe to rename without breaking imports or functionality
# Focuses on documentation, config files, and standalone tools

param(
    [switch]$DryRun = $false,
    [string]$LogFile = "conservative_organization_$(Get-Date -Format 'yyyy-MM-dd_HHmmss').csv"
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

function Test-SafeToRename {
    param([string]$FileName, [string]$FilePath)
    
    # Never rename these critical files
    if ($FileName -eq "__init__.py") { return $false }
    if ($FileName -eq "main.py") { return $false }
    if ($FileName -like "*service*.py" -and $FilePath -like "*backend*app*") { return $false }
    if ($FileName -like "*endpoint*.py" -and $FilePath -like "*backend*app*") { return $false }
    if ($FileName -like "requirements*.txt") { return $false }
    if ($FileName -like "package*.json") { return $false }
    if ($FileName -like "*config*.py") { return $false }
    
    # Safe file types
    if ($FileName -like "*.md") { return $true }  # Documentation is safe
    if ($FileName -like "config_*.json" -and $FilePath -like "*references*") { return $true }  # Reference configs are safe
    if ($FileName -like "*.py" -and $FilePath -like "*tools*" -and $FilePath -like "*backend*") { return $true }  # Backend tools are safe
    if ($FileName -match "^\d{4}-\d{2}-\d{2}-.*\.md$") { return $true }  # Date-prefixed docs are safe
    if ($FileName -like "test_*.py" -and $FilePath -like "*backend*") { return $true }  # Backend test files are safe
    
    return $false
}

function Get-SafeStandardizedName {
    param(
        [string]$OriginalName,
        [string]$FilePath
    )
    
    $ext = [System.IO.Path]::GetExtension($OriginalName)
    
    # Documentation files with dates at start
    if ($OriginalName -match "^(\d{4}-\d{2}-\d{2})-(.*)\.(md)$") {
        $date = $matches[1]
        $content = $matches[2] -replace "_", "-"
        if ($content -like "*audit*") { return "doc-audit-$date$ext" }
        if ($content -like "*summary*" -or $content -like "*implementation*") { return "doc-summary-$date$ext" }
        return "doc-$content-$date$ext"
    }
    
    # Config files in references (safe to rename)
    if ($OriginalName -match "^config_(.+)\.json$" -and $FilePath -like "*references*") {
        $configType = $matches[1] -replace "_", "-"
        return "config-$configType$ext"
    }
    
    # Documentation files with underscores
    if ($OriginalName -like "*.md" -and $OriginalName -match "_") {
        return $OriginalName -replace "_", "-"
    }
    
    # Backend test files (safer to rename than core files)
    if ($OriginalName -match "^test_(.+)\.py$" -and $FilePath -like "*backend*") {
        $testType = $matches[1] -replace "_", "-"
        return "test-$testType$ext"
    }
    
    # Backend tool files (standalone utilities)
    if ($FilePath -like "*backend*tools*" -and $OriginalName -like "*.py" -and $OriginalName -match "_") {
        $toolName = $OriginalName -replace "\.py$", "" -replace "_", "-"
        return "tool-$toolName$ext"
    }
    
    return $null  # No change needed
}

function Rename-FileSafely {
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
        SafetyCategory = ""
    }
    
    # Determine safety category
    if ($originalFile.Name -like "*.md") { $logEntry.SafetyCategory = "DOCUMENTATION" }
    elseif ($FilePath -like "*references*" -and $originalFile.Name -like "config_*.json") { $logEntry.SafetyCategory = "REFERENCE_CONFIG" }
    elseif ($FilePath -like "*backend*tools*") { $logEntry.SafetyCategory = "BACKEND_TOOL" }
    elseif ($originalFile.Name -like "test_*.py") { $logEntry.SafetyCategory = "TEST_FILE" }
    else { $logEntry.SafetyCategory = "OTHER" }
    
    try {
        if ($originalFile.Name -eq $NewName) {
            $logEntry.Status = "SKIPPED_SAME_NAME"
            $script:skippedCount++
            Write-Log "Skipped (same name): $($originalFile.Name)" "WARNING"
        }
        elseif (Test-Path $newPath) {
            $logEntry.Status = "SKIPPED_EXISTS"
            $logEntry.Error = "Target file already exists"
            $script:skippedCount++
            Write-Log "Skipped (exists): $($originalFile.Name) -> $NewName" "WARNING"
        }
        elseif ($DryRun) {
            $logEntry.Status = "DRY_RUN"
            $script:successCount++
            Write-Log "DRY RUN [$($logEntry.SafetyCategory)]: $($originalFile.Name) -> $NewName" "INFO"
        }
        else {
            Rename-Item -Path $FilePath -NewName $NewName -Force
            $logEntry.Status = "SUCCESS"
            $script:successCount++
            Write-Log "Renamed [$($logEntry.SafetyCategory)]: $($originalFile.Name) -> $NewName" "SUCCESS"
        }
    }
    catch {
        $logEntry.Status = "ERROR"
        $logEntry.Error = $_.Exception.Message
        $script:errorCount++
        Write-Log "Error renaming $($originalFile.Name): $($_.Exception.Message)" "ERROR"
    }
    
    return $logEntry
}

Write-Log "Starting conservative file organization (safe files only)" "INFO"
Write-Log "Mode: $(if($DryRun){'DRY RUN'}else{'ACTUAL RENAME'})" "INFO"

# Get only safe files for renaming
$safeFiles = Get-ChildItem -Path "." -Recurse -File | Where-Object { 
    (Test-SafeToRename -FileName $_.Name -FilePath $_.FullName) -and
    $_.FullName -notlike "*__pycache__*" -and
    $_.FullName -notlike "*node_modules*" -and
    $_.FullName -notlike "*build*"
}

Write-Log "Found $($safeFiles.Count) safe files that may need renaming" "INFO"

# Group by safety category for reporting
$categorizedFiles = $safeFiles | Group-Object { 
    if ($_.Name -like "*.md") { "DOCUMENTATION" }
    elseif ($_.FullName -like "*references*" -and $_.Name -like "config_*.json") { "REFERENCE_CONFIG" }
    elseif ($_.FullName -like "*backend*tools*") { "BACKEND_TOOL" }
    elseif ($_.Name -like "test_*.py") { "TEST_FILE" }
    else { "OTHER" }
}

foreach ($category in $categorizedFiles) {
    Write-Log "Category: $($category.Name) - $($category.Count) files" "INFO"
}

foreach ($file in $safeFiles) {
    $newName = Get-SafeStandardizedName -OriginalName $file.Name -FilePath $file.FullName
    
    if ($newName -and $newName -ne $file.Name) {
        $logData += Rename-FileSafely -FilePath $file.FullName -NewName $newName
    } else {
        Write-Log "Skipped (no change needed): $($file.Name)" "INFO"
        $skippedCount++
    }
}

# Export log
Write-Log "Exporting log to $LogFile..." "INFO"
$logData | Export-Csv -Path $LogFile -NoTypeInformation

# Summary
Write-Log "Conservative file organization completed!" "SUCCESS"
Write-Log "Total files processed: $($logData.Count)" "INFO"
Write-Log "Successfully renamed: $successCount" "SUCCESS"
Write-Log "Skipped: $skippedCount" "WARNING"
Write-Log "Errors: $errorCount" "ERROR"

if ($DryRun) {
    Write-Log "This was a DRY RUN. To apply changes, run without -DryRun flag" "INFO"
    Write-Log "`nSummary by category:" "INFO"
    $logData | Where-Object { $_.Status -eq "DRY_RUN" } | Group-Object SafetyCategory | ForEach-Object {
        Write-Host "  $($_.Name): $($_.Count) files" -ForegroundColor Cyan
    }
}

return $logData
