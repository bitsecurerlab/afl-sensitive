CPU_TARGET="i386"
cd qemu_mode/qemu-2.*.0
make clean || exit 1
make || exit 1

echo "[+] Build process successful!"

echo "[*] Copying binary..."

cp -f "${CPU_TARGET}-linux-user/qemu-${CPU_TARGET}" "../../afl-qemu-trace" || exit 1

