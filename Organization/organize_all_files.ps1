# Comprehensive File Organization Script
# Applies unified naming convention across the entire repository
# Pattern: {operation}-{database}-{collection}-{date}.{ext}

param(
    [switch]$DryRun = $false,
    [string]$LogFile = "file_organization_complete_$(Get-Date -Format 'yyyy-MM-dd_HHmmss').csv"
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

function Get-StandardizedName {
    param(
        [string]$OriginalName,
        [string]$Operation,
        [string]$Database = "",
        [string]$Collection = "",
        [string]$Date = ""
    )
    
    $ext = [System.IO.Path]::GetExtension($OriginalName)
    
    # Extract date if not provided
    if (-not $Date) {
        if ($OriginalName -match "(\d{4})[\-_]?(\d{2})[\-_]?(\d{2})") {
            $Date = "$($matches[1])-$($matches[2])-$($matches[3])"
        } elseif ($OriginalName -match "(\d{8})") {
            $dateStr = $matches[1]
            $Date = "$($dateStr.Substring(0,4))-$($dateStr.Substring(4,2))-$($dateStr.Substring(6,2))"
        } else {
            $Date = "unknown-date"
        }
    }
    
    # Build standardized name
    $parts = @()
    if ($Operation) { $parts += $Operation.ToLower() }
    if ($Database) { $parts += $Database.ToLower() }
    if ($Collection) { $parts += $Collection.ToLower() }
    if ($Date) { $parts += $Date }
    
    return ($parts -join "-") + $ext
}

function Rename-FileWithStandardization {
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
    }
    
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
            Write-Log "DRY RUN: $($originalFile.Name) -> $NewName" "INFO"
        }
        else {
            Rename-Item -Path $FilePath -NewName $NewName -Force
            $logEntry.Status = "SUCCESS"
            $script:successCount++
            Write-Log "Renamed: $($originalFile.Name) -> $NewName" "SUCCESS"
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

Write-Log "Starting comprehensive file organization" "INFO"
Write-Log "Mode: $(if($DryRun){'DRY RUN'}else{'ACTUAL RENAME'})" "INFO"

# 1. Test files in backend
Write-Log "Processing test files in backend..." "INFO"
$testFiles = Get-ChildItem -Path "backend" -Recurse -File | Where-Object { 
    $_.Name -like "test_*.py" -and $_.Name -notlike "*__pycache__*"
}

foreach ($file in $testFiles) {
    $operation = "test"
    $database = ""
    $collection = ""
    
    # Extract specifics from test file names
    if ($file.Name -match "test_(\w+)_(\w+)\.py") {
        $operation = "test"
        $database = $matches[1]
        $collection = $matches[2]
    }
    elseif ($file.Name -match "test_(\w+)\.py") {
        $operation = "test"
        $collection = $matches[1]
    }
    
    $newName = Get-StandardizedName -OriginalName $file.Name -Operation $operation -Database $database -Collection $collection
    $logData += Rename-FileWithStandardization -FilePath $file.FullName -NewName $newName
}

# 2. Config files in references
Write-Log "Processing config files in references..." "INFO"
$configFiles = Get-ChildItem -Path "references" -Recurse -File | Where-Object { 
    $_.Name -like "config_*.json"
}

foreach ($file in $configFiles) {
    $operation = "config"
    $collection = $file.Name -replace "config_", "" -replace "\.json$", ""
    $collection = $collection -replace "_", "-"
    
    $newName = Get-StandardizedName -OriginalName $file.Name -Operation $operation -Collection $collection
    $logData += Rename-FileWithStandardization -FilePath $file.FullName -NewName $newName
}

# 3. Comparison files
Write-Log "Processing comparison files..." "INFO"
$comparisonFiles = Get-ChildItem -Path "." -Recurse -File | Where-Object { 
    $_.Name -like "*comparison*" -and $_.Extension -eq ".json"
}

foreach ($file in $comparisonFiles) {
    $operation = "comparison"
    $collection = ""
    
    if ($file.Name -match "batch(\d+)") {
        $collection = "batch$($matches[1])"
    }
    
    $newName = Get-StandardizedName -OriginalName $file.Name -Operation $operation -Collection $collection
    $logData += Rename-FileWithStandardization -FilePath $file.FullName -NewName $newName
}

# 4. Tool files with specific naming
Write-Log "Processing tool files..." "INFO"
$toolFiles = Get-ChildItem -Path "backend\tools" -File | Where-Object { 
    $_.Name -like "*cleaning*" -or $_.Name -like "*preamble*"
}

foreach ($file in $toolFiles) {
    $operation = "tool"
    $collection = $file.BaseName -replace "_", "-"
    
    $newName = Get-StandardizedName -OriginalName $file.Name -Operation $operation -Collection $collection
    $logData += Rename-FileWithStandardization -FilePath $file.FullName -NewName $newName
}

# 5. Documentation files with dates
Write-Log "Processing documentation files..." "INFO"
$docFiles = Get-ChildItem -Path "." -Recurse -File | Where-Object { 
    ($_.Name -like "*audit*" -or $_.Name -like "*summary*" -or $_.Name -like "*implementation*") -and 
    $_.Extension -eq ".md" -and
    $_.Name -match "\d{4}[\-_]\d{2}[\-_]\d{2}"
}

foreach ($file in $docFiles) {
    $operation = "doc"
    $collection = ""
    
    if ($file.Name -like "*audit*") { $collection = "audit" }
    elseif ($file.Name -like "*summary*") { $collection = "summary" }
    elseif ($file.Name -like "*implementation*") { $collection = "implementation" }
    
    $newName = Get-StandardizedName -OriginalName $file.Name -Operation $operation -Collection $collection
    $logData += Rename-FileWithStandardization -FilePath $file.FullName -NewName $newName
}

# Export log
Write-Log "Exporting log to $LogFile..." "INFO"
$logData | Export-Csv -Path $LogFile -NoTypeInformation

# Summary
Write-Log "File organization completed!" "SUCCESS"
Write-Log "Total files processed: $($logData.Count)" "INFO"
Write-Log "Successfully renamed: $successCount" "SUCCESS"
Write-Log "Skipped: $skippedCount" "WARNING"
Write-Log "Errors: $errorCount" "ERROR"

if ($DryRun) {
    Write-Log "This was a DRY RUN. To apply changes, run without -DryRun flag" "INFO"
}

return $logData
