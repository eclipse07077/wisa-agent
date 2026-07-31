$ErrorActionPreference = "Stop"
$paperDir = $PSScriptRoot
$rootDir = Split-Path -Parent $paperDir
$buildDir = Join-Path $rootDir "tmp\pdfs\build"
$outputDir = Join-Path $rootDir "output\pdf"
New-Item -ItemType Directory -Force -Path $buildDir, $outputDir | Out-Null

function Check-Exit([string]$name) {
    if ($LASTEXITCODE -ne 0) {
        throw "$name failed with exit code $LASTEXITCODE"
    }
}

Push-Location $paperDir
try {
    & pdflatex "-interaction=nonstopmode" "-halt-on-error" "-file-line-error" "-output-directory=$buildDir" main.tex
    Check-Exit "pdflatex"
    Push-Location $buildDir
    try {
        $env:BIBINPUTS = $paperDir
        $env:BSTINPUTS = $paperDir
        & bibtex main
        Check-Exit "bibtex"
    } finally {
        Pop-Location
    }
    & pdflatex "-interaction=nonstopmode" "-halt-on-error" "-file-line-error" "-output-directory=$buildDir" main.tex
    Check-Exit "pdflatex"
    & pdflatex "-interaction=nonstopmode" "-halt-on-error" "-file-line-error" "-output-directory=$buildDir" main.tex
    Check-Exit "pdflatex"
} finally {
    Pop-Location
}

Copy-Item -LiteralPath (Join-Path $buildDir "main.pdf") -Destination (Join-Path $outputDir "paper.pdf") -Force
