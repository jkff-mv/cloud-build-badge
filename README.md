# Cloud Build Badge
[![build status](https://storage.googleapis.com/jkff-mv-laboratory-cloud-build-badge/triggers/7f7036fd-6d3e-470e-b57d-a3df19b16f5e/badge.svg)](https://github.com/jkff-mv/cloud-build-badge/blob/master/cloudbuild.yaml)
[![language](https://img.shields.io/badge/language-python-blue)](https://www.python.org/)
[![license](https://img.shields.io/badge/license-MIT%20License-lightgrey.svg)](https://github.com/jkff-mv/cloud-build-badge/blob/master/LICENSE)

## Overview
[Cloud Build](https://cloud.google.com/cloud-build/) のステータスを表すバッジを生成するアプリケーションです。  

![system overview](https://storage.googleapis.com/jkff-mv-laboratory-repository/cloud-build-badge/a7e16306-9363-4230-af12-e93a7b4ffd5d.png)

生成されるバッジはビルドのステータスに応じて6種類です。  

* ビルド中：working  
* ビルドの成功：success  
* ビルドの失敗：failure  
* ビルドのキャンセル：cancelled  
* ビルドのタイムアウト：timeout  
* ステップのタイムアウト：failed  

## Requirement
リポジトリの接続やCloud Buildの設定は済んでいることが前提となっています。  
未設定の場合は [公式ドキュメント](https://cloud.google.com/cloud-build/docs/automating-builds/create-manage-triggers) などを参考に設定してください。  

なお、接続されるリポジトリはCloud Source RepositoriesおよびGitHubにて正常に動作することを確認しています。  

## Setup

### Create Bucket
バッジの保存先であるCloud Storageのバケットを作成します。  

```
$ export BUCKET_NAME='your-bucket-name'
$ gsutil mb -c standard -l us-central1 gs://${BUCKET_NAME}
$ gsutil iam ch allUsers:objectViewer gs://${BUCKET_NAME}
```

### Deploy Function
バッジを生成するアプリケーションをCloud Functionsへデプロイします。  

```
$ export FUNCTION_NAME='any-function-name'
$ export BUCKET_NAME='your-bucket-name'
$ gcloud functions deploy ${FUNCTION_NAME} \
  --runtime python37 \
  --entry-point entry_point \
  --trigger-topic cloud-builds \
  --region us-central1 \
  --set-env-vars _CLOUD_BUILD_BADGE_BUCKET=${BUCKET_NAME}
```

## Usage

### Badge Location
バッジは2箇所に保存されます。  

Cloud Buildのトリガに対してブランチが1つしか設定されていない場合はこちらを参照ください。  

```
https://storage.googleapis.com/BUCKET/triggers/TRIGGER/badge.svg
```

Cloud Buildのトリガに対して複数のブランチが設定されている場合はこちらを参照ください。  
なお、ビルドの構成ファイル自体の構文エラーなどでビルドが失敗した場合、Cloud Functions内で対象のリポジトリ／ブランチの情報が取得できず、バッジが更新されないため注意してください。  

```
https://storage.googleapis.com/BUCKET/repositories/REPOSITORY/triggers/TRIGGER/branches/BRANCH/badge.svg
```

* `BUCKET` ：Cloud Storageのバケット名。  
* `TRIGGER` ：Cloud BuildのトリガID。  
* `REPOSITORY` ：ビルド対象のリポジトリ名。  
* `BRANCH` ：ビルド対象のブランチ名。  

### Customization
設定でバッジの保存先のバケットを切り替えたり、バッジのラベル部分を変更できます。  
Cloud Functionsの環境変数、もしくはCloud Buildのトリガの環境変数に値を設定してください。  
両方に設定が存在する場合、Cloud Buildのトリガ側の設定値が優先されます。  

|Variable|Type|Required|Default|Description|
|:--|:--|:-:|:--|:--|
|_CLOUD_BUILD_BADGE_BUCKET|string|○||バッジの保存先となるCloud Storageのバケット名です。|
|_CLOUD_BUILD_BADGE_LABEL|string||`build`|バッジのラベル部分に記載する文言です。|
|_CLOUD_BUILD_BADGE_LOGO|string|||バッジのラベル部分に表示するロゴです。<br>ロゴはData URI形式の画像として指定します。|
