This repo is self-deploying.

Changes to the config files or Kubernetes manifests in this repo will
be automatically deployed by Zuul after they merge.  This is the
preferred way to make changes.

To add new projects, edit zuul/main.yaml.

To add new node types, edit nodepool/nodepool.yaml.

# Debugging

Should something go wrong, these debugging tips may help to identify
and correct the problem.

Zuul consists of several related processes:

|zuul-scheduler   | the main decision-making process; 
|                 | listens to events and dispatches jobs
|zuul-executor    | runs jobs; this runs the Ansible processes which do the
|                 | work, but the actual work happens on ephemeral cloud nodes
|zuul-web         | serves the web interface
|nodepool-launcher| creates and deletes cloud resources as needed for
|                 | test nodes.

And this installation has one extra component not normally used in Zuul:

|gcloud-authdaemon| keeps updated credentials available to
|                 | zuul-executor for storing logs in Google Cloud
|                 | Storage

To obtain a `.kube/config` file suitable for using with `kubectl` run:

    gcloud container clusters get-credentials --project gerritcodereview-ci \
	       --zone us-central1-a zuul-control-plane

After that, verify it works by listing the Zuul pods:

```
$ kubectl -n zuul get pod
NAME                                     READY   STATUS    RESTARTS   AGE
gcloud-authdaemon-4klk5                  1/1     Running   0          23d
gcloud-authdaemon-jxcc4                  1/1     Running   0          23d
gcloud-authdaemon-p8x74                  1/1     Running   0          23d
nodepool-launcher-gcs-5755c9b745-hqmcz   1/1     Running   0          23d
zuul-executor-0                          1/1     Running   0          9d
zuul-scheduler-0                         1/1     Running   0          9d
zuul-web-548696d575-b4vrf                1/1     Running   0          9d
```

## Logs

All components log to stderr, so to see the logs, run something like:

    kubectl -n zuul logs zuul-scheduler-0

To trace events through the various components, there are two helpful
identifiers: the event ID and, once builds have been started, the
build ID.  Each event from Gerrit which arrives at Zuul is assigned a
unique ID by Zuul, and all subsequent logged actions related to that
event are associated with the event ID (or at least, that's the idea;
there may still be some log lines that are relevant but omit an event
ID -- if you come up short, you may need to expand your search scope).

An example entry with an event ID:

    2021-06-11 09:29:01,019 INFO zuul.Pipeline.gerrit.check: [e: a5d9669ace3b438782a05f82faa63daa] Adding change <Change 0x7ff3040a94c0 plugins/code-owners 309042,2> to queue <ChangeQueue check: plugins/code-owners> in <Pipeline check>

The event ID is in brackets and prefixed with "e:" for brevity.

An event ID may cause multiple builds of jobs to run.  You can narrow
build-related log entries down by using the build UUID.  Here's an example with both kinds of IDs:

    2021-06-11 09:57:54,464 INFO zuul.Scheduler: [e: a5d9669ace3b438782a05f82faa63daa] [build: 918d2c80e25c4f08a0f1c394cb188630] Build complete, result SUCCESS, warnings []

These IDs are useful for finding relevent entries within a single
component, as well as across components (for instance, as the
scheduler hands of processing of a build to the executor).

If you are debugging a problem with a job, the executor has the
ability to enable verbose logs from Ansible (equivalent to passing
-vvv to the ansible-playbook command).  To turn this on run:

    kubectl -n zuul exec zuul-executor-0 -- zuul-executor verbose
	
To disable it, run:

    kubectl -n zuul exec zuul-executor-0 -- zuul-executor unverbose

## Restarting

To perform a complete hard-restart of the system, run the following commands:

    kubectl -n zuul delete pod -l app.kubernetes.io/name=nodepool
    kubectl -n zuul delete pod -l app.kubernetes.io/name=zuul

This will delete all of the running pods, and Kubernetes will recreate
them from the deployment configuration.  Note that the scheduler takes
some time to become ready, and during this time the web interface may
be available but contain no data (it may say "Something went wrong" or
display error toasts).  You can monitor the progress with:

    kubectl -n zuul logs -f zuul-scheduler-0

The log line that indicates success is:

    2021-06-12 14:54:56,140 INFO zuul.Scheduler: Full reconfiguration complete (duration: 250.009 seconds)

And that also gives you an idea of how long the scheduler may take to
become ready.  At this point, you may need to reload the status page
in order for it to work.

(Note: Our current focus of Zuul development is an HA scheduler so
that all of Zuul can be restarted in a rolling fashion.)

# Additional Help

Feel free to contact James Blair (corvus) in Gerrit Slack, or the
wider Zuul community in #zuul on the OFTC IRC network, or the
zuul-discuss@lists.zuul-ci.org mailing list.

# Appendix: Manual steps for bootstrapping

These steps are not required for ongoing maintenance; they were
performed to initially prepare the environment.  Any changes should be
made to the declaritive code in this repo and automatically applied by
Zuul.

## Install certmanager

kubectl create namespace cert-manager
kubectl label namespace cert-manager certmanager.k8s.io/disable-validation=true
kubectl apply --validate=false -f https://github.com/jetstack/cert-manager/releases/download/v0.12.0/cert-manager.yaml
kubectl apply -n cert-manager -f letsencrypt.yaml

## Install mariadb

kubectl create namespace mariadb

Use Google cloud click to deploy
TODO: find a better HA sql database operator

kubectl port-forward svc/mariadb-mariadb --namespace mariadb 3306
mysql -h 127.0.0.1 -P 3306 -u root -p
create database zuul;
GRANT ALL PRIVILEGES ON zuul.* TO 'zuul'@'%' identified by '<password>' WITH GRANT OPTION;

## Install Zuul

gcloud compute addresses create zuul-static-ip --global
kubectl create namespace zuul

## Bind k8s service accounts to gcp service accounts
kubectl create serviceaccount --namespace zuul logs
kubectl create serviceaccount --namespace zuul nodepool
kubectl create serviceaccount --namespace zuul zuul

gcloud iam service-accounts add-iam-policy-binding \
  --role roles/iam.workloadIdentityUser \
  --member "serviceAccount:gerritcodereview-ci.svc.id.goog[zuul/logs]" \
  zuul-logs@gerritcodereview-ci.iam.gserviceaccount.com

gcloud iam service-accounts add-iam-policy-binding \
  --role roles/iam.workloadIdentityUser \
  --member "serviceAccount:gerritcodereview-ci.svc.id.goog[zuul/nodepool]" \
  nodepool@gerritcodereview-ci.iam.gserviceaccount.com

gcloud iam service-accounts add-iam-policy-binding \
  --role roles/iam.workloadIdentityUser \
  --member "serviceAccount:gerritcodereview-ci.svc.id.goog[zuul/zuul]" \
  zuul-63@gerritcodereview-ci.iam.gserviceaccount.com

kubectl annotate serviceaccount \
  --namespace zuul logs \
  iam.gke.io/gcp-service-account=zuul-logs@gerritcodereview-ci.iam.gserviceaccount.com

kubectl annotate serviceaccount \
  --namespace zuul nodepool \
  iam.gke.io/gcp-service-account=nodepool@gerritcodereview-ci.iam.gserviceaccount.com

kubectl annotate serviceaccount \
  --namespace zuul zuul \
  iam.gke.io/gcp-service-account=zuul-63@gerritcodereview-ci.iam.gserviceaccount.com

## Create a service account for self-deployment

kubectl -n zuul create serviceaccount zuul-deployment
kubectl create clusterrolebinding zuul-deployment-cluster-admin-binding \
  --clusterrole cluster-admin \
  --user system:serviceaccount:zuul:zuul-deployment
