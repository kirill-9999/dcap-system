#!/usr/bin/env pwsh
# Script for regenerating protobuf files
# Run: .\scripts\generate_proto.ps1

param(
    [switch]$Clean = $false
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  DCAP PROTO GENERATOR" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot
Write-Host "Project root: $ProjectRoot" -ForegroundColor Yellow
Write-Host ""

$ProtoFile = "proto/dcap/manager.proto"
if (-not (Test-Path $ProtoFile)) {
    Write-Host "ERROR: Proto file not found: $ProtoFile" -ForegroundColor Red
    exit 1
}
Write-Host "Proto file found: $ProtoFile" -ForegroundColor Green

try {
    python -c "import grpc_tools" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "grpcio-tools not found, installing..." -ForegroundColor Yellow
        pip install grpcio-tools
    }
    Write-Host "grpcio-tools available" -ForegroundColor Green
} catch {
    Write-Host "grpcio-tools not found, installing..." -ForegroundColor Yellow
    pip install grpcio-tools
}

if ($Clean) {
    Write-Host "Cleaning old files..." -ForegroundColor Yellow
    if (Test-Path "manager\src\proto_gen\dcap") {
        Remove-Item -Recurse -Force "manager\src\proto_gen\dcap" -ErrorAction SilentlyContinue
        Write-Host "   Removed: manager\src\proto_gen\dcap" -ForegroundColor Gray
    }
    if (Test-Path "dcap") {
        Remove-Item -Recurse -Force "dcap" -ErrorAction SilentlyContinue
        Write-Host "   Removed: dcap" -ForegroundColor Gray
    }
}

Write-Host "Creating directories..." -ForegroundColor Yellow
New-Item -ItemType Directory -Path "manager\src\proto_gen" -Force | Out-Null
New-Item -ItemType Directory -Path "dcap" -Force | Out-Null
Write-Host "Directories created" -ForegroundColor Green

Write-Host "Generating protobuf code..." -ForegroundColor Yellow
python -m grpc_tools.protoc -Iproto --python_out=manager/src/proto_gen --grpc_python_out=manager/src/proto_gen proto/dcap/manager.proto

if ($LASTEXITCODE -ne 0) {
    Write-Host "Generation failed!" -ForegroundColor Red
    exit 1
}
Write-Host "Protobuf generated successfully" -ForegroundColor Green

Write-Host "Copying to client directory..." -ForegroundColor Yellow
Copy-Item -Recurse -Path "manager\src\proto_gen\dcap\*" -Destination "dcap\" -Force
Write-Host "Files copied to dcap/" -ForegroundColor Green

Write-Host "Fixing imports in manager..." -ForegroundColor Yellow
$grpcFile = "manager\src\proto_gen\dcap\manager_pb2_grpc.py"
if (Test-Path $grpcFile) {
    $content = Get-Content $grpcFile -Raw
    $content = $content -replace 'from dcap import manager_pb2', 'from manager.src.proto_gen.dcap import manager_pb2'
    Set-Content $grpcFile $content -NoNewline
    Write-Host "Manager imports fixed" -ForegroundColor Green
} else {
    Write-Host "Manager file not found: $grpcFile" -ForegroundColor Yellow
}

Write-Host "Fixing imports in client..." -ForegroundColor Yellow
$grpcFile2 = "dcap\manager_pb2_grpc.py"
if (Test-Path $grpcFile2) {
    $content2 = Get-Content $grpcFile2 -Raw
    $content2 = $content2 -replace 'import dcap\.manager_pb2 as manager_pb2 as', 'import dcap.manager_pb2 as'
    Set-Content $grpcFile2 $content2 -NoNewline
    Write-Host "Client imports fixed" -ForegroundColor Green
} else {
    Write-Host "Client file not found: $grpcFile2" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Generated files:" -ForegroundColor Yellow
if (Test-Path "dcap\manager_pb2.py") {
    Write-Host "   OK: dcap\manager_pb2.py" -ForegroundColor Green
} else {
    Write-Host "   MISSING: dcap\manager_pb2.py" -ForegroundColor Red
}
if (Test-Path "dcap\manager_pb2_grpc.py") {
    Write-Host "   OK: dcap\manager_pb2_grpc.py" -ForegroundColor Green
} else {
    Write-Host "   MISSING: dcap\manager_pb2_grpc.py" -ForegroundColor Red
}
if (Test-Path "dcap\__init__.py") {
    Write-Host "   OK: dcap\__init__.py" -ForegroundColor Green
}

Write-Host ""
Write-Host "Available RPC methods:" -ForegroundColor Yellow
if (Test-Path $ProtoFile) {
    $methods = Select-String -Path $ProtoFile -Pattern 'rpc\s+(\w+)' | ForEach-Object { $_.Matches.Groups[1].Value }
    foreach ($method in $methods) {
        Write-Host "   - $method" -ForegroundColor Cyan
    }
} else {
    Write-Host "   Cannot read proto file" -ForegroundColor Red
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "PROTO GENERATION COMPLETE!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Restart Manager: python -m manager.src.main" -ForegroundColor White
Write-Host "  2. Run tests: python test_health.py" -ForegroundColor White