FROM postgres:18.2

COPY backup/hourly-backup.sh /usr/local/bin/hourly-backup.sh
COPY backup/verify-latest-restore.sh /usr/local/bin/verify-latest-restore.sh

RUN sed -i 's/\r$//' \
      /usr/local/bin/hourly-backup.sh \
      /usr/local/bin/verify-latest-restore.sh \
    && chmod 0755 /usr/local/bin/hourly-backup.sh /usr/local/bin/verify-latest-restore.sh

ENTRYPOINT ["/usr/local/bin/hourly-backup.sh"]
