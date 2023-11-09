Please refer to this link for permanently changing client's /etc/resolv.conf file.

Link: https://kifarunix.com/make-permanent-dns-changes-on-resolv-conf-in-linux/

# Configuring Client's /etc/resolv.conf permanently

You may follow the tutorial for resolvconf the link gives and make changes according to your setup.

### In the tutorial, please change this:
``` sudo nano /etc/resolvconf/resolv.conf.d/base ```
### to this:
``` sudo nano /etc/resolvconf/resolv.conf.d/head ```

The first one did not work when I followed the tutorial, but the second one worked.

I only follow the resolvconf part, and I did not do other settings besides resolvconf.

Don't forget to reboot your system after setting up the resolvconf.

After rebooting, you should see your client's/etc/resolv.conf file is overwritten.


