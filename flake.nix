{
  description = "Downloader development shell (yt-dlp, ffmpeg, python)";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs {
          inherit system;
        };

        isLinux = system == "x86_64-linux" || system == "aarch64-linux";

        commonInputs = [
          pkgs.python3
          pkgs.python3Packages.yt-dlp
          pkgs.ffmpeg
          pkgs.atomicparsley
          pkgs.python3Packages.pillow
        ];

        guiInputs = if isLinux then [
          pkgs.python3Packages.pyqt6
          pkgs.qt6.qtbase
          pkgs.qt6.qtwayland
        ] else [
          pkgs.python3Packages.pyqt6
          pkgs.qt6.qtbase
        ];
      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = commonInputs ++ guiInputs;

          shellHook = ''
            echo "Downloader environment loaded!"
            echo "System: ${system}"
            echo "Python version: $(python --version)"
            echo "yt-dlp version: $(yt-dlp --version)"
            echo "ffmpeg version: $(ffmpeg -version | head -n 1)"
          '';
        };
      }
    );
}
