FROM hashicorp/vault:1.15

COPY config.hcl /vault/config/config.hcl

EXPOSE 8200

ENTRYPOINT ["vault"]
CMD ["server", "-config=/vault/config/config.hcl"]
