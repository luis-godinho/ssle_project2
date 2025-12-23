{
  description = "SSLE Project 2 - Attack Tolerance Mechanisms (BFT + MTD)";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = nixpkgs.legacyPackages.${system};

        # Python environment with all dependencies
        pythonEnv = pkgs.python311.withPackages (
          ps: with ps; [
            flask
            requests
            prometheus-client
            pytest
            pytest-cov
            black
            pylint
            mypy
          ]
        );

      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            docker
            docker-compose
            pythonEnv
            curl
            jq
          ];
        };

        packages.default = pkgs.stdenv.mkDerivation {
          name = "ssle-project2";
          src = ./.;

          installPhase = ''
            mkdir -p $out
            cp -r . $out/
          '';
        };
      }
    );
}
