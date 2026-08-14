#!/usr/bin/env fish

# Exit immediately if the compilation fails
echo "🛠️  Compiling sketch..."
arduino-cli compile
if test $status -ne 0
    echo "❌ Compilation failed. Please fix your code errors first."
    exit 1
end

echo "✅ Compilation successful!"
echo "🔄 Starting upload loop on $PORT..."

# Loop indefinitely until the upload command succeeds
set attempt 1
while true
    echo "⚡ Upload attempt #$attempt..."

    # Run the upload
    arduino-cli upload
    if test $status -eq 0
        echo "🎉 Upload succeeded on attempt #$attempt!"
        break
    else
        echo "⚠️  Upload failed. Retrying in 2 seconds..."
        set attempt (math $attempt + 1)
        sleep 2
    end
end

