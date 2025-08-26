# File Renaming Script for Unified Naming Convention
# Applies consistent naming: {operation}-{database}-{collection}-{date}.{ext}

$renameLog = @()

function Rename-MetadataFile {
    param(
        [string]$SourcePath,
        [string]$NewName,
        [string]$Description
    )
    
    try {
        $sourceFile = Get-Item $SourcePath -ErrorAction Stop
        $targetPath = Join-Path $sourceFile.Directory $NewName
        
        if (Test-Path $targetPath) {
            Write-Warning "Target file already exists: $targetPath"
            return $false
        }
        
        Rename-Item $SourcePath $NewName -ErrorAction Stop
        $script:renameLog += [PSCustomObject]@{
            Original = $sourceFile.Name
            New = $NewName
            Path = $sourceFile.Directory.FullName
            Description = $Description
            Status = "Success"
        }
        Write-Host "Renamed: $($sourceFile.Name) -> $NewName" -ForegroundColor Green
        return $true
    }
    catch {
        $script:renameLog += [PSCustomObject]@{
            Original = (Split-Path $SourcePath -Leaf)
            New = $NewName
            Path = (Split-Path $SourcePath -Parent)
            Description = $Description
            Status = "Failed: $($_.Exception.Message)"
        }
        Write-Host "Failed to rename: $SourcePath - $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
}

Write-Host "Starting file renaming with unified naming convention..." -ForegroundColor Cyan
Write-Host "Convention: {operation}-{database}-{collection}-{date}.{ext}" -ForegroundColor Yellow
Write-Host ""

# Backend API Metadata Files
$metadataPath = "D:\DigiFloat\LawChronicle\backend\app\api\metadata"
if (Test-Path $metadataPath) {
    Write-Host "Processing Backend API Metadata Files..." -ForegroundColor Cyan
    
    # Individual batch files
    Get-ChildItem "$metadataPath\metadata_batch_*_20250819_*.json" | ForEach-Object {
        if ($_.Name -match "metadata_batch_(\d+)_20250819_\d+\.json") {
            $batchNum = $matches[1]
            $newName = "merge-date-enriched-batch$batchNum-2025-08-19.json"
            Rename-MetadataFile $_.FullName $newName "Phase4 Date Merge - Batch $batchNum"
        }
    }
    
    # Batch cleaning file
    $cleaningFile = "$metadataPath\metadata_batch_cleaning_Batched-Statutes_batch_3_batch_7_batch_1_batch_10_batch_6_batch_2_batch_4_batch_9_batch_8_batch_5_2025-08-15.json"
    if (Test-Path $cleaningFile) {
        Rename-MetadataFile $cleaningFile "cleaning-batched-statutes-all-batches-2025-08-15.json" "Phase3 Batch Cleaning - All Batches"
    }
    
    # Generated metadata
    $generatedFile = "$metadataPath\metadata_generated_Batched-Statutes_batch__2025-08-15.json"
    if (Test-Path $generatedFile) {
        Rename-MetadataFile $generatedFile "generated-batched-statutes-all-2025-08-15.json" "Generated Metadata - All Batches"
    }
    
    # Split metadata
    $splitFile = "$metadataPath\metadata_split_Batched-Statutes_batch__2025-08-15.json"
    if (Test-Path $splitFile) {
        Rename-MetadataFile $splitFile "split-batched-statutes-all-2025-08-15.json" "Split Processing - All Batches"
    }
    
    # Pakistan validation files
    $validationAllFile = "$metadataPath\metadata_pakistan_validation_validation_Batched-Statutes_batch__all_2025-08-15.json"
    if (Test-Path $validationAllFile) {
        Rename-MetadataFile $validationAllFile "validation-batched-statutes-all-2025-08-15.json" "Pakistan Validation - All Batches"
    }
    
    $validationBatch1File = "$metadataPath\metadata_pakistan_validation_validation_Batched-Statutes_batch__batches_1_2025-08-15.json"
    if (Test-Path $validationBatch1File) {
        Rename-MetadataFile $validationBatch1File "validation-batched-statutes-batch1-2025-08-15.json" "Pakistan Validation - Batch 1"
    }
    
    # Raw statutes normalization
    $rawNormFile = "$metadataPath\metadata_Statutes_raw_statutes_to_normalised_2025-08-14_19-43-22.json"
    if (Test-Path $rawNormFile) {
        Rename-MetadataFile $rawNormFile "normalization-statutes-raw-to-normalized-2025-08-14.json" "Database Normalization - Raw to Normalized"
    }
}

# Backend Root Metadata
$backendMetadataPath = "D:\DigiFloat\LawChronicle\backend\metadata"
if (Test-Path $backendMetadataPath) {
    Write-Host "Processing Backend Root Metadata Files..." -ForegroundColor Cyan
    
    Get-ChildItem "$backendMetadataPath\metadata_batch_*_20250819_*.json" | ForEach-Object {
        if ($_.Name -match "metadata_batch_(\d+)_20250819_\d+\.json") {
            $batchNum = $matches[1]
            $newName = "merge-date-enriched-batch$batchNum-2025-08-19.json"
            Rename-MetadataFile $_.FullName $newName "Phase4 Date Merge - Batch $batchNum (Root)"
        }
    }
}

Write-Host ""
Write-Host "Renaming Summary:" -ForegroundColor Cyan
$renameLog | Group-Object Status | ForEach-Object {
    $color = if ($_.Name -eq "Success") { "Green" } else { "Red" }
    Write-Host "  $($_.Name): $($_.Count) files" -ForegroundColor $color
}

Write-Host ""
Write-Host "Detailed Rename Log:" -ForegroundColor Cyan
$renameLog | Format-Table Original, New, Description, Status -AutoSize

# Save log to file
$logPath = "D:\DigiFloat\LawChronicle\file_rename_log.csv"
$renameLog | Export-Csv $logPath -NoTypeInformation
Write-Host "Detailed log saved to: $logPath" -ForegroundColor Green

Write-Host ""
Write-Host "Naming Convention Applied:" -ForegroundColor Green
Write-Host "  Date Format: YYYY-MM-DD (day precision only)" -ForegroundColor White
Write-Host "  Separator: Hyphens for readability" -ForegroundColor White
Write-Host "  Structure: {operation}-{database}-{collection}-{date}.{ext}" -ForegroundColor White
Write-Host "  Context: Operation type and target clearly identified" -ForegroundColor White
Write-Host "  Length: Concise while maintaining clarity" -ForegroundColor White

Write-Host ""
Write-Host "File organization complete!" -ForegroundColor Green
