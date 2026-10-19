# 台帳契約 schema 2

UTF-8 JSON。完成した架空例はexamples/ledger.json。schema 1の自動変換はしない。旧台帳を保管し、schemaを2へ変更したコピーで引用review・依存関係・必須項目を点検する。旧validを意味レビューに引き継がない。

## トップ

schema=2、title、question、stopped、log（非空文字列配列）、sourcesとclaims（非空配列）、baselineが必須。baselineはstatus=unread/partial/read、sources（既知source key文字列配列）、claims（既知主張text配列）。前回メモを読んだことと、前回調査を再検証したことをlogで区別する。

baseline.claim_statesは任意配列。各要素はid、status、conclusion、source_keysが必須、review_statesは任意。同じclaim IDの現在status・conclusion（省略時text）・根拠key集合と比較する。配列順・重複は集合比較で無視。review_statesが前回にあれば現在review状態集合とも比較。change_reasonは人が変更理由を記す。文字列・集合の変化であり、意味差分・改版本文差分・因果の自動判定ではない。

## Source

id、key、title、url、accessed（YYYY-MM-DD）、edition、period、kind、scope、read_ranges、lineage、access、limitationが必須。版や年代が不明ならunknown等を明記する。

- kind: catalog/index/body。catalog/indexのscopeはmetadataのみ。
- scope: metadata/partial/full。fullは保存文の量ではなく、何を読了したかをread_ranges/limitationで明記する。提供された抜粋の読了を原本全体の読了とはしない。
- access: ok/blocked/unavailable。未取得でも所在レコードは残せるが、引用根拠には使えない。
- url: HTTP/S、ローカル元資料のfile URI、または`local:保存コピーの相対パス`。file URIは空ホスト/localhost・絶対パス・query/fragmentなし。ローカル方式はfileとsha256を必須とする。URIは記録だけで取得しない。公開可能な架空例はlocal方式を使う。
- fileとsha256: 保存コピーへの相対POSIXパスと64文字の小文字SHA-256を組で記録。親参照、絶対パス、Windows drive/ADS、backslash、外へのsymlinkを拒否。UTF-8の保存文のhashは生バイト、引用照合はCRLFをLFへ揃えて1始まりの行で扱う。ledgerは5MB、各保存文は10MBまで。
- lineage: 原典グループIDの配列。不明は空。既知の派生資料はderived_fromにsource IDを置き、lineageを空にして依存元の原典グループを継承する。未知参照と循環を拒否。同じグループを重複計上しないが、実際の相互独立性は証明しない。複数原典を束ねた系列はuncertainとして独立数に加えない。

## Claimと引用リンク

id、text、status、novelty、conflicts、evidenceが必須。status=unverified/partial/supported/contestedは調査者の申告。novelty=none/candidate/added-to-reviewed-baseline。conflictsは他のclaim ID配列。conclusion、change_reason、next_checks、counterevidence_searchは任意。

counterevidence_search=not_recorded（既定）/incomplete/completed。completedも自己申告であり網羅性保証ではない。実際の探索語、範囲、未探索はlogへ残す。

各evidenceはsource、start、end（1始まり・両端含む）、quote、role=support/refute/context、use=metadata/bodyを持つ。quoteは保存文の指定行と完全一致させ、省略記号による部分照合はしない。

reviewは任意objectで、state=unreviewed（省略時の扱い）/accepted/rejected。accepted/rejectedはreviewerとnoteが必須。担当名は役割等でもよく、私的な氏名を公開用台帳へ含めない。原文の文脈・対象・版・年代を照合して支持可否を判断した理由を書く。レビューをしていない場合は未記入かunreviewedとし、形式照合成功からacceptedを生成しない。

supportedでも未レビュー支持しかなければ出力はno_reviewed_support。未レビューを含めばnot_reviewed、却下を含めばcontains_rejected_links。recorded_accepted_support_linksは承認記録のある支持リンク数のみ。recorded_origin_group_countもそのリンクだけを対象にした記録上のグループ数。誤ったacceptedや誤系列は自動で見抜けない。

反証またはconflictsが記録されていればcontestedが必要。contestedと、その矛盾相手にはnext_checksのtarget/question/reasonを最低1件記録する。反証が無関係と判断した場合も、勝手に削除せずlogに判断と理由を保存して関係を更新する。次の資料の所在を捏造しない。

added-to-reviewed-baselineにはbaseline=read、少なくとも1件のaccepted支持、既知text集合にないことを要する。この検査は新発見の保証ではない。

## 出力

verification.jsonのvalid/formal_validは形式整合の同義。semantic_guaranteeはfalse。失敗時は構造化errorsのみを成果とし、HTMLとdelta.jsonは作らない。成功時はreport.htmlとdelta.jsonを作る。全記録にはURL・レビュー担当等を含むため、公開前に別途点検する。

形が不正な入力は依存関係やファイルを処理する前に拒否する。未知の追加フィールドは評価せず、形式成功時の全記録にそのままエスケープ表示する。JSONキー重複、空資料集合、空主張集合は拒否する。
